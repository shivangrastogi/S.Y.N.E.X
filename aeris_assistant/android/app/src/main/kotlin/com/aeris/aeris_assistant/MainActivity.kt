package com.aeris.aeris_assistant

import android.content.Context
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

/** The app's screen. It borrows the process-wide engine instead of owning one (see [AerisEngine]). */
class MainActivity : FlutterActivity() {
    override fun provideFlutterEngine(context: Context): FlutterEngine =
        AerisEngine.obtain(context, intent?.getStringExtra("route"))

    /** Closing the screen must not stop AERIS (the call watcher still needs it). */
    override fun shouldDestroyEngineWithHost(): Boolean = false
}
