package com.shivang.aeris.core.stt

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import org.vosk.android.StorageService
import timber.log.Timber
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Fully offline STT via Vosk. We load *both* a Hindi and an English-India model
 * and run whichever has higher confidence on each utterance — this is how we
 * approximate Hinglish without a multilingual model (Vosk doesn't ship one
 * small enough to comfortably bundle on phones).
 *
 * Models live in `filesDir/vosk/<lang>/...` and are unpacked from `assets/`
 * the first time the app runs (see [unpackIfNeeded]).
 */
@Singleton
class SttEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    sealed interface Status {
        data object Idle : Status
        data object Loading : Status
        data object Listening : Status
        data class Error(val message: String) : Status
    }

    private val _status = MutableStateFlow<Status>(Status.Idle)
    val status: StateFlow<Status> = _status.asStateFlow()

    private var enModel: Model? = null
    private var hiModel: Model? = null
    private var activeService: SpeechService? = null

    suspend fun ensureLoaded() = withContext(Dispatchers.IO) {
        if (enModel != null && hiModel != null) return@withContext
        _status.value = Status.Loading
        try {
            enModel = unpackIfNeeded("vosk-model-small-en-in-0.4")
            hiModel = unpackIfNeeded("vosk-model-small-hi-0.22")
            _status.value = Status.Idle
        } catch (t: Throwable) {
            Timber.e(t, "STT model load failed")
            _status.value = Status.Error(t.message ?: "Failed to load STT models")
        }
    }

    private suspend fun unpackIfNeeded(name: String): Model = withContext(Dispatchers.IO) {
        val target = File(context.filesDir, "vosk/$name")
        if (!target.exists() || target.list().isNullOrEmpty()) {
            // StorageService.unpack writes the asset folder into the app's filesDir.
            return@withContext suspendUnpack(name)
        }
        Model(target.absolutePath)
    }

    private suspend fun suspendUnpack(name: String): Model =
        kotlinx.coroutines.suspendCancellableCoroutine { cont ->
            StorageService.unpack(
                context, name, "vosk",
                { model -> cont.resumeWith(Result.success(model)) },
                { ex -> cont.resumeWith(Result.failure(ex)) },
            )
        }

    /**
     * Stream partial + final transcripts. Each emission is a [Transcript] —
     * caller decides what to do with partials vs finals.
     */
    fun listen(language: Lang = Lang.AUTO): Flow<Transcript> = callbackFlow {
        val model = when (language) {
            Lang.HI -> hiModel
            Lang.EN -> enModel
            Lang.AUTO -> enModel // English-India model handles code-switched speech reasonably
        } ?: run {
            close(IllegalStateException("STT model not loaded — call ensureLoaded() first"))
            return@callbackFlow
        }
        val recognizer = Recognizer(model, 16000.0f)
        val listener = object : RecognitionListener {
            override fun onPartialResult(hypothesis: String?) {
                hypothesis?.let { parsePartial(it)?.let { p -> trySend(Transcript(p, false)) } }
            }
            override fun onResult(hypothesis: String?) {
                hypothesis?.let { parseFinal(it)?.let { f -> trySend(Transcript(f, true)) } }
            }
            override fun onFinalResult(hypothesis: String?) {
                hypothesis?.let { parseFinal(it)?.let { f -> trySend(Transcript(f, true)) } }
                close()
            }
            override fun onError(exception: Exception?) {
                Timber.e(exception, "Vosk error")
                close(exception)
            }
            override fun onTimeout() { close() }
        }
        try {
            val service = SpeechService(recognizer, 16000.0f)
            activeService = service
            service.startListening(listener)
            _status.value = Status.Listening
            awaitClose {
                runCatching { service.stop() }
                runCatching { service.shutdown() }
                runCatching { recognizer.close() }
                activeService = null
                _status.value = Status.Idle
            }
        } catch (t: Throwable) {
            recognizer.close()
            close(t)
        }
    }.flowOn(Dispatchers.IO)

    fun stop() {
        runCatching { activeService?.stop() }
    }

    private fun parsePartial(json: String): String? = runCatching {
        JSONObject(json).optString("partial").takeIf { it.isNotBlank() }
    }.getOrNull()

    private fun parseFinal(json: String): String? = runCatching {
        JSONObject(json).optString("text").takeIf { it.isNotBlank() }
    }.getOrNull()

    enum class Lang { AUTO, HI, EN }
    data class Transcript(val text: String, val isFinal: Boolean)
}
