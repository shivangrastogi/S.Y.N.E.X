package com.aeris.aeris_remote

import android.app.Activity
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.AudioManager
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.provider.Settings
import android.text.TextUtils
import android.util.DisplayMetrics
import android.view.KeyEvent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream

// Native screen capture for "laptop sees phone screen" (Phase 3).
// MethodChannel aeris/screencap:
//   ensurePermission() -> Bool      (pops the OS screen-record dialog once)
//   captureOnce()      -> ByteArray (one JPEG frame of the whole screen)
class MainActivity : FlutterActivity() {

    private val CHANNEL = "aeris/screencap"
    private val VIDEO_CHANNEL = "aeris/video"
    private val A11Y_CHANNEL = "aeris/a11y"
    private val ASSIST_CHANNEL = "aeris/assist"
    private val APPS_CHANNEL = "aeris/apps"
    private val REQ_CODE = 4242
    private var videoDecoder: VideoDecoder? = null
    // Phase A6: set when the OS launches us via the assist gesture (power-
    // button hold / "assistant" button). Dart consumes it → starts listening.
    private var assistPending = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action == Intent.ACTION_ASSIST) assistPending = true
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.action == Intent.ACTION_ASSIST) {
            assistPending = true
            // App already running → nudge Dart immediately.
            flutterEngine?.dartExecutor?.binaryMessenger?.let {
                MethodChannel(it, ASSIST_CHANNEL).invokeMethod("assist", null)
            }
        }
    }

    private var projectionManager: MediaProjectionManager? = null
    private var projection: MediaProjection? = null
    private var pendingPermission: MethodChannel.Result? = null
    // Android 14+: a MediaProjection allows createVirtualDisplay() ONCE. So we
    // build the mirror + reader a single time and reuse them for every frame.
    private var reader: ImageReader? = null
    private var vDisplay: VirtualDisplay? = null
    private var capW = 0
    private var capH = 0

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        projectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                as MediaProjectionManager

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "ensurePermission" -> {
                        if (projection != null) {
                            result.success(true)
                        } else {
                            pendingPermission = result
                            startActivityForResult(
                                projectionManager!!.createScreenCaptureIntent(),
                                REQ_CODE)
                        }
                    }
                    "captureOnce" -> captureOnce(result)
                    // WebRTC screen share (flutter_webrtc getDisplayMedia) needs
                    // a mediaProjection foreground service RUNNING before it calls
                    // getMediaProjection — the plugin doesn't start one itself, so
                    // Dart starts it just before getDisplayMedia and stops it after.
                    "startScreenService" -> {
                        try {
                            val i = Intent(this, ScreenCaptureService::class.java)
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                                startForegroundService(i)
                            else
                                startService(i)
                            result.success(true)
                        } catch (e: Exception) {
                            result.success(false)
                        }
                    }
                    "stopScreenService" -> {
                        try {
                            stopService(
                                Intent(this, ScreenCaptureService::class.java))
                        } catch (_: Exception) {}
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }

        // H.264 live-video decoder → Flutter Texture (Phase 4d).
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, VIDEO_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "init" -> {
                        val w = call.argument<Int>("width") ?: 0
                        val h = call.argument<Int>("height") ?: 0
                        try {
                            if (videoDecoder == null) {
                                videoDecoder = VideoDecoder(flutterEngine.renderer)
                            }
                            val texId = videoDecoder!!.init(w, h)
                            result.success(texId)
                        } catch (e: Exception) {
                            result.error("VDEC", e.message, null)
                        }
                    }
                    "feed" -> {
                        val au = call.arguments as? ByteArray
                        if (au != null) videoDecoder?.feed(au)
                        result.success(null)
                    }
                    "dispose" -> {
                        videoDecoder?.dispose()
                        videoDecoder = null
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }

        // Phase A5: screen control via the AccessibilityService + media keys.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, A11Y_CHANNEL)
            .setMethodCallHandler { call, result ->
                val svc = AerisAccessibilityService.instance
                when (call.method) {
                    "isEnabled" -> result.success(isA11yEnabled())
                    "openSettings" -> {
                        startActivity(Intent(
                            Settings.ACTION_ACCESSIBILITY_SETTINGS)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                        result.success(true)
                    }
                    "readScreen" -> result.success(svc?.readScreen() ?: "")
                    "tap" -> result.success(
                        svc?.tapByText(call.argument<String>("text") ?: "")
                            ?: false)
                    "scroll" -> result.success(
                        svc?.scroll(call.argument<Boolean>("forward") ?: true)
                            ?: false)
                    "global" -> result.success(
                        svc?.global(call.argument<String>("action") ?: "")
                            ?: false)
                    "media" -> {
                        mediaKey(call.argument<String>("key") ?: "")
                        result.success(true)
                    }
                    // Phase 10: the phone agent's numbered-element interface.
                    "dumpUi" -> result.success(svc?.dumpUi() ?: "")
                    "clickId" -> result.success(
                        svc?.clickId(call.argument<Int>("id") ?: -1) ?: false)
                    "longClickId" -> result.success(
                        svc?.longClickId(call.argument<Int>("id") ?: -1) ?: false)
                    "typeId" -> result.success(
                        svc?.typeId(call.argument<Int>("id") ?: -1,
                            call.argument<String>("text") ?: "") ?: false)
                    "pressEnter" -> result.success(svc?.pressEnter() ?: false)
                    else -> result.notImplemented()
                }
            }

        // Phase A9: launch ANY installed app by fuzzy label (not just a map).
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, APPS_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    // Label lookups touch every installed app (slow on a full
                    // phone) — off the main thread, or the UI freezes (ANR).
                    "launch" -> {
                        val q = call.argument<String>("query") ?: ""
                        Thread {
                            val pkg = findPackageByLabel(q)
                            runOnUiThread {
                                result.success(pkg != null && launchPackage(pkg))
                            }
                        }.start()
                    }
                    "list" -> Thread {
                        val labels = appLabels().keys.sorted()
                        runOnUiThread { result.success(labels) }
                    }.start()
                    "whatsappLatestImage" -> result.success(
                        whatsappLatestImage(call.argument<String>("phone") ?: ""))
                    else -> result.notImplemented()
                }
            }

        // Phase A6: hand off the "launched by assist gesture" flag to Dart.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, ASSIST_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "consume" -> {
                        val v = assistPending
                        assistPending = false
                        result.success(v)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun isA11yEnabled(): Boolean {
        val flat = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        val me = "$packageName/$packageName.AerisAccessibilityService"
        val splitter = TextUtils.SimpleStringSplitter(':')
        splitter.setString(flat)
        for (s in splitter) if (s.equals(me, ignoreCase = true)) return true
        return false
    }

    // label → package for every launcher app. loadLabel() is slow (it reads
    // each app's resources), so the map is cached for 10 minutes and only
    // ever built on a background thread.
    @Volatile private var labelCache: Map<String, String>? = null
    @Volatile private var labelCacheAt = 0L

    private fun appLabels(): Map<String, String> {
        val now = System.currentTimeMillis()
        labelCache?.let { if (now - labelCacheAt < 10 * 60_000) return it }
        val main = Intent(Intent.ACTION_MAIN, null)
            .addCategory(Intent.CATEGORY_LAUNCHER)
        val map = HashMap<String, String>()
        for (ri in packageManager.queryIntentActivities(main, 0)) {
            map[ri.loadLabel(packageManager).toString()] =
                ri.activityInfo.packageName
        }
        labelCache = map
        labelCacheAt = now
        return map
    }

    // Match a spoken app name to an installed launcher app's package.
    private fun findPackageByLabel(query: String): String? {
        val q = query.lowercase().trim()
        if (q.isEmpty()) return null
        var bestPkg: String? = null
        var bestScore = -1
        for ((rawLabel, pkg) in appLabels()) {
            val label = rawLabel.lowercase()
            val score = when {
                label == q -> 100
                label.startsWith(q) -> 80
                label.contains(q) -> 60
                q.contains(label) && label.length >= 3 -> 45
                else -> -1
            }
            if (score > bestScore) {
                bestScore = score
                bestPkg = pkg
            }
        }
        return if (bestScore >= 45) bestPkg else null
    }

    private fun launchPackage(pkg: String): Boolean {
        val launch = packageManager.getLaunchIntentForPackage(pkg) ?: return false
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(launch)
        return true
    }

    // Phase 10: open the WhatsApp chat for [phone] (digits, with country code)
    // with the newest gallery image (last 15 min) attached — WhatsApp's
    // preview screen then only needs "Send". Returns an error string or "".
    private fun whatsappLatestImage(phone: String): String {
        val digits = phone.filter { it.isDigit() }
        if (digits.isEmpty()) return "no phone number"
        val since = System.currentTimeMillis() / 1000 - 15 * 60
        val uri = try {
            contentResolver.query(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                arrayOf(MediaStore.Images.Media._ID),
                "${MediaStore.Images.Media.DATE_ADDED} >= ?",
                arrayOf(since.toString()),
                "${MediaStore.Images.Media.DATE_ADDED} DESC"
            )?.use { c ->
                if (c.moveToFirst()) ContentUris.withAppendedId(
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI, c.getLong(0))
                else null
            }
        } catch (e: SecurityException) {
            return "no photo permission"
        } ?: return "no image saved in the last 15 minutes"
        val pkg = listOf("com.whatsapp", "com.whatsapp.w4b").firstOrNull {
            packageManager.getLaunchIntentForPackage(it) != null
        } ?: return "WhatsApp not installed"
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "image/*"
            setPackage(pkg)
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra("jid", "$digits@s.whatsapp.net")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return try {
            startActivity(send)
            ""
        } catch (e: Exception) {
            e.message ?: "could not open WhatsApp"
        }
    }

    private fun mediaKey(key: String) {
        val code = when (key) {
            "playpause" -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
            "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "prev" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            "stop" -> KeyEvent.KEYCODE_MEDIA_STOP
            else -> return
        }
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code))
        am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_CODE) {
            if (resultCode == Activity.RESULT_OK && data != null) {
                // Capture into a non-null local — the nullable `data` param
                // is not smart-cast inside the lambda below.
                val projData: Intent = data
                // Android 14+: a mediaProjection foreground service MUST be
                // running before getMediaProjection() or it throws.
                startForegroundService(
                    Intent(this, ScreenCaptureService::class.java))
                Handler(Looper.getMainLooper()).postDelayed({
                    try {
                        projection = projectionManager!!
                            .getMediaProjection(resultCode, projData)
                        // Android 14+ REQUIRES a callback registered before
                        // createVirtualDisplay(), else it throws
                        // "Must register a callback before starting capture".
                        projection?.registerCallback(
                            object : MediaProjection.Callback() {
                                override fun onStop() {
                                    releaseCapture()
                                    projection = null
                                }
                            }, Handler(Looper.getMainLooper()))
                        pendingPermission?.success(true)
                    } catch (e: Exception) {
                        pendingPermission?.success(false)
                    }
                    pendingPermission = null
                }, 300)
            } else {
                pendingPermission?.success(false)
                pendingPermission = null
            }
        }
    }

    private fun captureOnce(result: MethodChannel.Result) {
        val proj = projection
        if (proj == null) {
            result.success(null)
            return
        }
        // Build the mirror + reader ONCE and keep them alive. Android 14+ throws
        // if createVirtualDisplay() is called a second time on the same
        // projection, so every subsequent capture reuses this same pipeline.
        if (vDisplay == null || reader == null) {
            val metrics = DisplayMetrics()
            windowManager.defaultDisplay.getRealMetrics(metrics)
            capW = metrics.widthPixels
            capH = metrics.heightPixels
            val density = metrics.densityDpi
            try {
                reader = ImageReader.newInstance(
                    capW, capH, PixelFormat.RGBA_8888, 2)
                vDisplay = proj.createVirtualDisplay(
                    "aeris-cap", capW, capH, density,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                    reader!!.surface, null, null)
            } catch (e: Exception) {
                releaseCapture()
                result.success(null)
                return
            }
        }

        val r = reader
        if (r == null) {
            result.success(null)
            return
        }
        // Give the mirror a moment to render a fresh frame, then grab it.
        Handler(Looper.getMainLooper()).postDelayed({
            var bytes: ByteArray? = null
            try {
                val image: Image? = r.acquireLatestImage()
                if (image != null) {
                    bytes = imageToJpeg(image, capW, capH)
                    image.close()
                }
            } catch (_: Exception) {
            }
            // NOTE: do NOT release the display/reader — reused next capture.
            result.success(bytes)
        }, 400)
    }

    private fun releaseCapture() {
        try { vDisplay?.release() } catch (_: Exception) {}
        try { reader?.close() } catch (_: Exception) {}
        vDisplay = null
        reader = null
    }

    override fun onDestroy() {
        try { videoDecoder?.dispose() } catch (_: Exception) {}
        videoDecoder = null
        releaseCapture()
        try { projection?.stop() } catch (_: Exception) {}
        projection = null
        super.onDestroy()
    }

    private fun imageToJpeg(image: Image, w: Int, h: Int): ByteArray {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * w
        val bmp = Bitmap.createBitmap(
            w + rowPadding / pixelStride, h, Bitmap.Config.ARGB_8888)
        bmp.copyPixelsFromBuffer(buffer)
        val cropped = if (rowPadding == 0) bmp
            else Bitmap.createBitmap(bmp, 0, 0, w, h)
        // Downscale the wide dimension to ~1080 to keep the payload small.
        val scale = if (cropped.width > 1080) 1080f / cropped.width else 1f
        val out = if (scale < 1f)
            Bitmap.createScaledBitmap(cropped,
                (cropped.width * scale).toInt(),
                (cropped.height * scale).toInt(), true)
        else cropped
        val baos = ByteArrayOutputStream()
        out.compress(Bitmap.CompressFormat.JPEG, 60, baos)
        return baos.toByteArray()
    }
}
