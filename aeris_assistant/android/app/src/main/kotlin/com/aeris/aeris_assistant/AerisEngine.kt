package com.aeris.aeris_assistant

import android.content.Context
import com.aeris.aeris_assistant.calls.CallBridge
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.FlutterEngineCache
import io.flutter.embedding.engine.dart.DartExecutor

/**
 * The one Flutter engine (= the one Dart world: store, voice, brain) for the
 * whole app process.
 *
 * Normally the engine dies with the screen. AERIS also has to work while the
 * screen is closed — the call watcher answers calls by voice in the
 * background — so the engine is owned by the process instead: [MainActivity]
 * borrows it when it opens, and [com.aeris.aeris_assistant.calls.CallWatchService]
 * keeps the process (and so the engine) alive.
 */
object AerisEngine {
    private const val ENGINE_ID = "aeris"

    /** The running engine, created (and its Dart `main()` started) on first use. */
    fun obtain(context: Context, initialRoute: String? = null): FlutterEngine {
        FlutterEngineCache.getInstance().get(ENGINE_ID)?.let { return it }

        val appContext = context.applicationContext
        val engine = FlutterEngine(appContext) // also registers every plugin
        CallBridge.attach(engine, appContext)
        DeviceBridge.attach(engine, appContext) // volume, media keys, ringer, next alarm, installed apps
        // e.g. `adb shell am start ... --es route /voicecheck` (features/settings/voice_check.dart)
        initialRoute?.let { engine.navigationChannel.setInitialRoute(it) }
        engine.dartExecutor.executeDartEntrypoint(DartExecutor.DartEntrypoint.createDefault())
        FlutterEngineCache.getInstance().put(ENGINE_ID, engine)
        return engine
    }
}
