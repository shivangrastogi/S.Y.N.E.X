package com.aeris.aeris_remote

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import android.view.Surface
import io.flutter.view.TextureRegistry
import java.nio.ByteBuffer
import java.util.ArrayDeque

// Hardware H.264 decoder → Flutter Texture (Phase 4d, 60 fps live screen).
//
// The laptop streams raw Annex-B H.264 access units over the LAN socket.
// Dart hands each AU to feed(); MediaCodec decodes straight onto a Surface
// backed by a Flutter SurfaceTexture, so frames reach the GPU with no
// bitmap copy. Parameter sets (SPS/PPS) are in-band (one keyframe/second),
// so we just configure with mime+size and feed complete AUs.
class VideoDecoder(private val textures: TextureRegistry) {

    private var entry: TextureRegistry.SurfaceTextureEntry? = null
    private var codec: MediaCodec? = null
    private var surface: Surface? = null

    private val lock = Object()
    private val auQueue = ArrayDeque<ByteArray>()   // data waiting for a buffer
    private val availIn = ArrayDeque<Int>()          // buffers waiting for data
    private var started = false
    private var frames = 0
    private val TAG = "AerisVideo"

    /** Create the texture + decoder, return the Flutter texture id. */
    fun init(width: Int, height: Int): Long {
        Log.i(TAG, "init($width x $height)")
        dispose()
        val e = textures.createSurfaceTexture()
        entry = e
        val st = e.surfaceTexture()
        st.setDefaultBufferSize(width, height)
        val sfc = Surface(st)
        surface = sfc

        val fmt = MediaFormat.createVideoFormat("video/avc", width, height)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try { fmt.setInteger(MediaFormat.KEY_LOW_LATENCY, 1) } catch (_: Exception) {}
        }
        val c = MediaCodec.createDecoderByType("video/avc")
        Log.i(TAG, "decoder = ${c.name}")
        frames = 0
        c.setCallback(object : MediaCodec.Callback() {
            override fun onInputBufferAvailable(mc: MediaCodec, index: Int) {
                synchronized(lock) { availIn.addLast(index); pump() }
            }
            override fun onOutputBufferAvailable(
                mc: MediaCodec, index: Int, info: MediaCodec.BufferInfo) {
                try { mc.releaseOutputBuffer(index, true) } catch (_: Exception) {}
                if (frames == 0) Log.i(TAG, "FIRST decoded frame rendered")
                frames++
            }
            override fun onError(mc: MediaCodec, e: MediaCodec.CodecException) {
                Log.e(TAG, "codec error: ${e.message} (recoverable=${e.isRecoverable})")
            }
            override fun onOutputFormatChanged(mc: MediaCodec, format: MediaFormat) {
                Log.i(TAG, "output format: $format")
            }
        })
        c.configure(fmt, sfc, null, 0)
        c.start()
        codec = c
        started = true
        Log.i(TAG, "decoder started, textureId=${e.id()}")
        return e.id()
    }

    /** Queue one access unit; paired with a codec input buffer ASAP. */
    fun feed(au: ByteArray) {
        synchronized(lock) {
            if (!started) return
            // Slow decoder / WiFi burst — cap the backlog so we stay live.
            while (auQueue.size > 30) auQueue.removeFirst()
            auQueue.addLast(au)
            pump()
        }
    }

    // Caller holds `lock`. Feed as many (buffer,data) pairs as we can.
    private fun pump() {
        val c = codec ?: return
        while (availIn.isNotEmpty() && auQueue.isNotEmpty()) {
            val index = availIn.removeFirst()
            val au = auQueue.removeFirst()
            val buf: ByteBuffer = try {
                c.getInputBuffer(index) ?: continue
            } catch (_: Exception) { continue }
            buf.clear()
            buf.put(au)
            try {
                c.queueInputBuffer(index, 0, au.size, 0, 0)
            } catch (_: Exception) {}
        }
    }

    fun dispose() {
        synchronized(lock) {
            started = false
            auQueue.clear()
            availIn.clear()
        }
        try { codec?.stop() } catch (_: Exception) {}
        try { codec?.release() } catch (_: Exception) {}
        codec = null
        try { surface?.release() } catch (_: Exception) {}
        surface = null
        try { entry?.release() } catch (_: Exception) {}
        entry = null
    }
}
