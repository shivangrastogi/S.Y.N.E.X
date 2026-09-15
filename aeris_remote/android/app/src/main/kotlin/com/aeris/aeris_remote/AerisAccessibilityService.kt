package com.aeris.aeris_remote

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

// Phase A5 — the screen-control superpower. Once the user enables AERIS under
// Settings → Accessibility, this service lets AERIS read the current screen,
// tap elements by their visible text, scroll, and hit global buttons (back/
// home/recents/notifications) inside ANY app.
//
// MainActivity reaches it through the companion `instance`. All methods run on
// the main thread (the method-channel handler is already there), so no locking.
class AerisAccessibilityService : AccessibilityService() {

    companion object {
        @JvmStatic
        var instance: AerisAccessibilityService? = null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        instance = null
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        instance = null
        super.onDestroy()
    }

    // We don't react to events; AERIS pulls state on demand.
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    /** Visible text of the foreground screen, top-to-bottom, deduped. */
    fun readScreen(): String {
        val root = rootInActiveWindow ?: return ""
        val items = ArrayList<Pair<Int, String>>()
        val seen = HashSet<String>()
        collect(root, items, seen)
        items.sortBy { it.first }
        val sb = StringBuilder()
        for (p in items) {
            sb.append(p.second).append('\n')
            if (sb.length > 4000) break
        }
        return sb.toString().trim()
    }

    private fun collect(
        node: AccessibilityNodeInfo?,
        out: ArrayList<Pair<Int, String>>,
        seen: HashSet<String>
    ) {
        if (node == null) return
        val raw = node.text ?: node.contentDescription
        if (raw != null) {
            val t = raw.toString().trim()
            if (t.length in 1..200 && seen.add(t)) {
                val r = Rect()
                node.getBoundsInScreen(r)
                out.add(Pair(r.top, t))
            }
        }
        for (i in 0 until node.childCount) collect(node.getChild(i), out, seen)
    }

    /** Tap the first element whose text/description contains [query]. */
    fun tapByText(query: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val target = findByText(root, query.lowercase()) ?: return false
        var n: AccessibilityNodeInfo? = target
        while (n != null) {
            if (n.isClickable) {
                return n.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
            n = n.parent
        }
        // Nothing clickable in the chain — click the match itself anyway.
        return target.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    private fun findByText(
        node: AccessibilityNodeInfo?,
        q: String
    ): AccessibilityNodeInfo? {
        if (node == null) return null
        val raw = node.text ?: node.contentDescription
        if (raw != null && raw.toString().lowercase().contains(q)) return node
        for (i in 0 until node.childCount) {
            val hit = findByText(node.getChild(i), q)
            if (hit != null) return hit
        }
        return null
    }

    /** Scroll the first scrollable node forward/backward. */
    fun scroll(forward: Boolean): Boolean {
        val root = rootInActiveWindow ?: return false
        val s = findScrollable(root) ?: return false
        val action = if (forward)
            AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        else
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        return s.performAction(action)
    }

    private fun findScrollable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.isScrollable) return node
        for (i in 0 until node.childCount) {
            val hit = findScrollable(node.getChild(i))
            if (hit != null) return hit
        }
        return null
    }

    /** back | home | recents | notifications | quick_settings | screenshot */
    fun global(which: String): Boolean {
        val action = when (which) {
            "back" -> GLOBAL_ACTION_BACK
            "home" -> GLOBAL_ACTION_HOME
            "recents" -> GLOBAL_ACTION_RECENTS
            "notifications" -> GLOBAL_ACTION_NOTIFICATIONS
            "quick_settings" -> GLOBAL_ACTION_QUICK_SETTINGS
            "screenshot" -> GLOBAL_ACTION_TAKE_SCREENSHOT // API 28+
            else -> return false
        }
        return performGlobalAction(action)
    }
}
