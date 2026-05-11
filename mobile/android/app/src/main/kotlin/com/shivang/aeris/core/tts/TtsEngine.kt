package com.shivang.aeris.core.tts

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber
import java.util.Locale
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Wrapper around Android's built-in TTS. Picks hi-IN if a Hindi voice is
 * installed, otherwise falls back to en-IN, otherwise system default.
 *
 * Works fully offline once the user has downloaded the language voice via
 * Settings → Language → Speech (Android 13+ does this automatically).
 */
@Singleton
class TtsEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val _isSpeaking = MutableStateFlow(false)
    val isSpeaking: StateFlow<Boolean> = _isSpeaking.asStateFlow()

    private var tts: TextToSpeech? = null
    private var ready = false

    init { initEngine() }

    private fun initEngine() {
        tts = TextToSpeech(context) { status ->
            if (status != TextToSpeech.SUCCESS) {
                Timber.w("TTS init failed: %d", status)
                return@TextToSpeech
            }
            val hi = Locale("hi", "IN")
            val en = Locale("en", "IN")
            val target = when {
                tts?.isLanguageAvailable(hi) == TextToSpeech.LANG_AVAILABLE -> hi
                tts?.isLanguageAvailable(en) == TextToSpeech.LANG_AVAILABLE -> en
                else -> Locale.getDefault()
            }
            tts?.language = target
            tts?.setSpeechRate(1.0f)
            tts?.setPitch(1.0f)
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) { _isSpeaking.value = true }
                override fun onDone(utteranceId: String?) { _isSpeaking.value = false }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) { _isSpeaking.value = false }
            })
            ready = true
        }
    }

    fun speak(text: String) {
        if (text.isBlank()) return
        if (!ready) { Timber.w("TTS not ready, dropping: %s", text); return }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString())
    }

    fun stop() {
        tts?.stop()
        _isSpeaking.value = false
    }

    fun shutdown() {
        runCatching { tts?.stop(); tts?.shutdown() }
        tts = null
        ready = false
    }
}
