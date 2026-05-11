package com.shivang.aeris.core.llm

import android.content.Context
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import com.google.mediapipe.tasks.genai.llminference.LlmInferenceSession
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Thin wrapper around MediaPipe's on-device LLM Inference API. Loads a Gemma
 * (.task) model from local storage. The model file is *not* bundled — the user
 * places it via Settings (recommended path: app's filesDir/models/).
 *
 * Status flow lets the UI show "Loading brain…" while the model warms up.
 */
@Singleton
class LlmEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    sealed interface Status {
        data object Idle : Status
        data object Loading : Status
        data object Ready : Status
        data class Error(val message: String) : Status
    }

    private val _status = MutableStateFlow<Status>(Status.Idle)
    val status: StateFlow<Status> = _status.asStateFlow()

    private var inference: LlmInference? = null

    suspend fun load(modelPath: String) = withContext(Dispatchers.IO) {
        try {
            _status.value = Status.Loading
            val file = File(modelPath)
            check(file.exists()) { "Model file not found at $modelPath" }
            inference?.close()
            val opts = LlmInference.LlmInferenceOptions.builder()
                .setModelPath(modelPath)
                .setMaxTokens(1024)
                .setMaxNumImages(0)
                .build()
            inference = LlmInference.createFromOptions(context, opts)
            _status.value = Status.Ready
            Timber.i("LLM loaded: %s", file.name)
        } catch (t: Throwable) {
            Timber.e(t, "LLM load failed")
            _status.value = Status.Error(t.message ?: "Failed to load model")
        }
    }

    fun isReady(): Boolean = _status.value is Status.Ready

    /** Streaming token output — collect on the UI to render typing-effect chat. */
    fun generateStream(prompt: String): Flow<String> = callbackFlow {
        val infer = inference ?: run {
            close(IllegalStateException("LLM not loaded"))
            return@callbackFlow
        }
        val sessionOpts = LlmInferenceSession.LlmInferenceSessionOptions.builder()
            .setTopK(40)
            .setTemperature(0.7f)
            .build()
        val session = LlmInferenceSession.createFromOptions(infer, sessionOpts)
        try {
            session.addQueryChunk(prompt)
            session.generateResponseAsync { partial, done ->
                trySend(partial)
                if (done) close()
            }
            awaitClose { runCatching { session.close() } }
        } catch (t: Throwable) {
            session.close()
            close(t)
        }
    }.flowOn(Dispatchers.IO)

    suspend fun generate(prompt: String): String = withContext(Dispatchers.IO) {
        val infer = inference ?: throw IllegalStateException("LLM not loaded")
        infer.generateResponse(prompt)
    }

    fun shutdown() {
        runCatching { inference?.close() }
        inference = null
        _status.value = Status.Idle
    }
}
