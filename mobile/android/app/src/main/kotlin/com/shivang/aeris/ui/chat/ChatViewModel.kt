package com.shivang.aeris.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shivang.aeris.core.brain.Brain
import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.llm.LlmEngine
import com.shivang.aeris.core.stt.SttEngine
import com.shivang.aeris.core.tts.TtsEngine
import com.shivang.aeris.data.SettingsRepo
import com.shivang.aeris.data.repo.ChatRepo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatBubble(val role: String, val text: String, val streaming: Boolean = false)

data class ChatUiState(
    val bubbles: List<ChatBubble> = emptyList(),
    val partialTranscript: String = "",
    val isListening: Boolean = false,
    val isSpeaking: Boolean = false,
    val brainStatus: LlmEngine.Status = LlmEngine.Status.Idle,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val brain: Brain,
    private val stt: SttEngine,
    private val tts: TtsEngine,
    private val llm: LlmEngine,
    private val chatRepo: ChatRepo,
    private val settings: SettingsRepo,
) : ViewModel() {

    private val partial = MutableStateFlow("")
    private val ephemeral = MutableStateFlow<List<ChatBubble>>(emptyList())
    private var listenJob: Job? = null

    val ui: StateFlow<ChatUiState> = combine(
        chatRepo.observeRecent().map { msgs -> msgs.map { ChatBubble(it.role, it.text) } },
        ephemeral, partial, stt.status, tts.isSpeaking, llm.status,
    ) { arr ->
        @Suppress("UNCHECKED_CAST")
        val stored = arr[0] as List<ChatBubble>
        @Suppress("UNCHECKED_CAST")
        val live = arr[1] as List<ChatBubble>
        val p = arr[2] as String
        val sttSt = arr[3] as SttEngine.Status
        val speaking = arr[4] as Boolean
        val brainSt = arr[5] as LlmEngine.Status
        ChatUiState(
            bubbles = stored + live,
            partialTranscript = p,
            isListening = sttSt is SttEngine.Status.Listening,
            isSpeaking = speaking,
            brainStatus = brainSt,
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, ChatUiState())

    private val _visionTrigger = MutableStateFlow(0)
    val visionTrigger: StateFlow<Int> = _visionTrigger.asStateFlow()

    init {
        viewModelScope.launch {
            val path = settings.modelPath.first()
            if (!path.isNullOrBlank() && llm.status.value !is LlmEngine.Status.Ready) {
                llm.load(path)
            }
        }
        viewModelScope.launch { stt.ensureLoaded() }
    }

    fun toggleListen() {
        if (listenJob?.isActive == true) {
            stt.stop()
            listenJob = null
            return
        }
        listenJob = viewModelScope.launch {
            stt.listen().collect { t ->
                if (t.isFinal) {
                    partial.value = ""
                    if (t.text.isNotBlank()) submit(t.text)
                } else {
                    partial.value = t.text
                }
            }
        }
    }

    fun submit(text: String) = viewModelScope.launch {
        chatRepo.appendUser(text)
        when (val reply = brain.route(text)) {
            is Brain.Reply.Skill -> {
                chatRepo.appendAeris(reply.reply.display)
                tts.speak(reply.reply.spoken)
                if (reply.reply.event is BrainEvent.VisionTriggered) {
                    _visionTrigger.value = _visionTrigger.value + 1
                }
            }
            is Brain.Reply.LlmStream -> {
                val sb = StringBuilder()
                val bubble = ChatBubble("aeris", "", streaming = true)
                ephemeral.value = listOf(bubble)
                reply.tokens.collect { tok ->
                    sb.append(tok)
                    ephemeral.value = listOf(bubble.copy(text = sb.toString()))
                }
                val finalText = sb.toString().trim()
                ephemeral.value = emptyList()
                if (finalText.isNotEmpty()) {
                    chatRepo.appendAeris(finalText)
                    tts.speak(finalText)
                }
            }
            is Brain.Reply.Error -> {
                chatRepo.appendAeris(reply.message)
                tts.speak(reply.message)
            }
        }
    }

    fun clear() = viewModelScope.launch { chatRepo.clear() }
}
