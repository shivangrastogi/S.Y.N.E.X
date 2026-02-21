// Path: d:\New folder (2) - JARVIS\android-app\app\src\main\java\com\example\jarvis\jarvismobile\JarvisAccessibilityService.kt
package com.example.jarvis.jarvismobile

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent
import android.util.Log
import android.content.Intent

class JarvisAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        Log.d("JarvisAS", "Accessibility Service Connected")
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}

    fun performAutomation(action: String, target: String?, data: Map<String, Any>?) {
        when (action) {
            "unlock" -> unlockPhone()
            "click" -> {
                val x = (data?.get("x") as? Number)?.toFloat() ?: 500f
                val y = (data?.get("y") as? Number)?.toFloat() ?: 500f
                clickOnScreen(x, y)
            }
            "open_app" -> target?.let { openApp(it) }
        }
    }

    fun unlockPhone() {
        Log.d("JarvisAS", "Attempting to unlock phone via Swipe Up")
        performSwipeUp()
    }

    fun performSwipeUp() {
        // Simple swipe up to trigger PIN entry or unlock
        val swipePath = Path()
        swipePath.moveTo(540f, 2000f) // Start from bottom center
        swipePath.lineTo(540f, 1000f) // Swipe up to middle
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(swipePath, 0, 400))
            .build()
        
        dispatchGesture(gesture, null, null)
    }

    fun clickOnScreen(x: Float, y: Float) {
        val clickPath = Path()
        clickPath.moveTo(x, y)
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(clickPath, 0, 50))
            .build()
        
        dispatchGesture(gesture, null, null)
    }

    private fun openApp(packageName: String) {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
        launchIntent?.let {
            it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(it)
        }
    }

    companion object {
        var instance: JarvisAccessibilityService? = null
    }
}
