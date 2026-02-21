package com.jarvis.mobile.network

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.AudioManager
import android.util.Log
import kotlinx.coroutines.*
import java.io.IOException

class CallAudioBridge(private val context: Context) {
    private val TAG = "CallAudioBridge"
    private var isRunning = false
    private var scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    // Audio Configuration
    private val SAMPLE_RATE = 16000
    private val CHANNEL_CONFIG_IN = AudioFormat.CHANNEL_IN_MONO
    private val CHANNEL_CONFIG_OUT = AudioFormat.CHANNEL_OUT_MONO
    private val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    private val BUFFER_SIZE = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG_IN, AUDIO_FORMAT) * 2

    private var audioRecord: AudioRecord? = null
    private var audioTrack: AudioTrack? = null

    @SuppressLint("MissingPermission")
    fun start() {
        if (isRunning) return
        isRunning = true
        Log.d(TAG, "Starting Audio Bridge...")

        // 1. Setup AudioTrack (Speaker)
        val trackSize = AudioTrack.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG_OUT, AUDIO_FORMAT)
        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(Utils.getAudioAttributes())
            .setAudioFormat(Utils.getAudioFormat(SAMPLE_RATE))
            .setBufferSizeInBytes(trackSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        audioTrack?.play()

        // 2. Setup AudioRecord (Microphone)
        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION, // Tuned for VoIP
            SAMPLE_RATE,
            CHANNEL_CONFIG_IN,
            AUDIO_FORMAT,
            BUFFER_SIZE
        )
        
        if (audioRecord?.state == AudioRecord.STATE_INITIALIZED) {
            audioRecord?.startRecording()
            startCaptureLoop()
        } else {
            Log.e(TAG, "AudioRecord initialization failed")
        }
    }

    private fun startCaptureLoop() {
        scope.launch {
            val buffer = ByteArray(BUFFER_SIZE)
            while (isRunning && isActive) {
                val read = audioRecord?.read(buffer, 0, BUFFER_SIZE) ?: 0
                if (read > 0) {
                    // Send to backend
                    ConnectionManager.sendBinary(buffer.copyOfRange(0, read))
                }
            }
        }
    }

    fun onAudioReceived(data: ByteArray) {
        if (!isRunning) return
        try {
            audioTrack?.write(data, 0, data.size)
        } catch (e: Exception) {
            Log.e(TAG, "Error playing audio", e)
        }
    }

    fun stop() {
        isRunning = false
        scope.cancel()
        scope = CoroutineScope(Dispatchers.IO + SupervisorJob()) // Reset scope
        
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {}
        
        try {
            audioTrack?.stop()
            audioTrack?.release()
        } catch (e: Exception) {}
        
        audioRecord = null
        audioTrack = null
        Log.d(TAG, "Audio Bridge Stopped")
    }
}

object Utils {
    // Helper to get AudioAttributes for Call
    fun getAudioAttributes(): android.media.AudioAttributes {
        return android.media.AudioAttributes.Builder()
            .setUsage(android.media.AudioAttributes.USAGE_VOICE_COMMUNICATION)
            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()
    }
    
    fun getAudioFormat(sampleRate: Int): AudioFormat {
        return AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(sampleRate)
            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            .build()
    }
}
