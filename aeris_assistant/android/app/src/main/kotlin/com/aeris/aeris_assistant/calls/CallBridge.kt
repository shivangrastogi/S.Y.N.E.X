package com.aeris.aeris_assistant.calls

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * Dart ⇄ Android for calls. Dart side: lib/calls/call_bridge.dart.
 *
 *   method channel `aeris/calls`         Dart asks Android to do something
 *   event channel  `aeris/calls/events`  Android reports ringing / answered / ended
 */
object CallBridge {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var eventSink: EventChannel.EventSink? = null

    /** An event that arrived before Dart started listening (e.g. right after a cold start). */
    private var undeliveredEvent: Map<String, Any>? = null

    fun attach(engine: FlutterEngine, appContext: Context) {
        val messenger = engine.dartExecutor.binaryMessenger
        MethodChannel(messenger, "aeris/calls").setMethodCallHandler { call, result ->
            fun bool(name: String) = call.argument<Boolean>(name) == true
            fun text(name: String) = call.argument<String>(name) ?: ""
            when (call.method) {
                "startWatching" -> {
                    CallWatchService.start(appContext)
                    result.success(true)
                }
                "stopWatching" -> {
                    CallWatchService.stop(appContext)
                    result.success(true)
                }
                "isWatching" -> result.success(CallWatchService.isRunning)
                "answer" -> result.success(CallControl.answer(appContext, bool("speaker")))
                "reject" -> result.success(CallControl.reject(appContext))
                "sendText" -> result.success(CallControl.sendText(appContext, text("number"), text("text")))
                "silenceRinger" -> {
                    CallControl.silenceRinger(appContext, (call.argument<Int>("fadeMs") ?: 0).toLong())
                    result.success(null)
                }
                "restoreRinger" -> {
                    CallControl.restoreRinger(appContext, (call.argument<Int>("fadeMs") ?: 0).toLong())
                    result.success(null)
                }
                "glow" -> {
                    val state = text("state")
                    if (state == "off") EdgeGlowOverlay.hide(appContext)
                    else EdgeGlowOverlay.show(appContext, GlowState.valueOf(state.uppercase()))
                    result.success(null)
                }
                "glowLevel" -> {
                    EdgeGlowOverlay.setLevel((call.argument<Double>("level") ?: 0.0).toFloat())
                    result.success(null)
                }
                "audioSituation" -> result.success(CallAudio.situation(appContext))
                "likelyCallers" -> result.success(CallerLookup.likelyCallers(appContext, call.argument<Int>("limit") ?: 40))
                "canDrawOverlays" -> result.success(EdgeGlowOverlay.canDraw(appContext))
                "openOverlaySettings" -> {
                    appContext.startActivity(
                        Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${appContext.packageName}"))
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        // AERIS's voice while the phone rings (lib/voice/local/ringing_voice_player.dart)
        MethodChannel(messenger, "aeris/ringing_voice").setMethodCallHandler { call, result ->
            when (call.method) {
                "play" -> RingingVoicePlayer.play(
                    appContext,
                    call.argument<String>("path") ?: "",
                    call.argument<Boolean>("earbudsOnly") == true,
                ) { played -> mainHandler.post { result.success(played) } }
                "stop" -> {
                    RingingVoicePlayer.stop()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        EventChannel(messenger, "aeris/calls/events").setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, sink: EventChannel.EventSink) {
                eventSink = sink
                undeliveredEvent?.let(sink::success)
                undeliveredEvent = null
            }

            override fun onCancel(arguments: Any?) {
                eventSink = null
            }
        })
    }

    /** Sends `{type, ...extra}` to Dart (always on the main thread, as Flutter requires). */
    fun emit(type: String, extra: Map<String, Any> = emptyMap()) {
        val event = mapOf("type" to type) + extra
        mainHandler.post {
            val sink = eventSink
            if (sink != null) sink.success(event) else undeliveredEvent = event
        }
    }
}
