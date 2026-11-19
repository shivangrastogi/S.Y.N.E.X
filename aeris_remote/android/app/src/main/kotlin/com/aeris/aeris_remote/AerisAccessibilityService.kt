package com.aeris.aeris_remote

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
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

    // ── Phase 10: phone agent ──────────────────────────────────────────
    // The agent (lib/phone_agent.dart) sees the screen as a numbered list of
    // elements and acts by number. `uiNodes` holds the nodes from the most
    // recent dumpUi(); ids index into it until the next dump.
    private val uiNodes = ArrayList<AccessibilityNodeInfo>()

    /** Numbered list of the foreground screen's visible, labelled or
     *  actionable elements, e.g. `[7] Button "Send" tap`. First line = app. */
    fun dumpUi(): String {
        uiNodes.clear()
        val root = rootInActiveWindow ?: return ""
        val sb = StringBuilder()
        sb.append("app: ").append(root.packageName ?: "?").append('\n')
        walkUi(root, sb)
        return sb.toString().trim()
    }

    private fun walkUi(node: AccessibilityNodeInfo?, sb: StringBuilder) {
        if (node == null || sb.length > 7000 || uiNodes.size >= 160) return
        if (!node.isVisibleToUser) return
        val label = labelOf(node)
        val acts = ArrayList<String>()
        if (node.isClickable) acts.add("tap")
        if (node.isLongClickable) acts.add("long_press")
        if (node.isEditable) acts.add("type")
        if (node.isScrollable) acts.add("scroll")
        if (node.isCheckable) acts.add(if (node.isChecked) "checked" else "unchecked")
        if (label.isNotEmpty() || acts.isNotEmpty()) {
            val id = uiNodes.size
            uiNodes.add(node)
            val cls = node.className?.toString()?.substringAfterLast('.') ?: "View"
            sb.append('[').append(id).append("] ").append(cls)
            if (label.isNotEmpty()) sb.append(" \"").append(label).append('"')
            if (acts.isNotEmpty()) sb.append(' ').append(acts.joinToString(","))
            sb.append('\n')
        }
        for (i in 0 until node.childCount) walkUi(node.getChild(i), sb)
    }

    /** text → description → hint → view-id, trimmed to one short line. */
    private fun labelOf(n: AccessibilityNodeInfo): String {
        var raw: CharSequence? = n.text ?: n.contentDescription
        if (raw == null && Build.VERSION.SDK_INT >= 26) raw = n.hintText
        var s = raw?.toString()?.replace('\n', ' ')?.trim() ?: ""
        if (s.isEmpty()) {
            val vid = n.viewIdResourceName?.substringAfterLast('/') ?: ""
            if (vid.isNotEmpty()) s = "id:$vid"
        }
        return if (s.length > 80) s.substring(0, 80) + "…" else s
    }

    private fun uiNode(id: Int): AccessibilityNodeInfo? =
        uiNodes.getOrNull(id)?.also { it.refresh() }

    /** Tap element [id]: nearest clickable ancestor, else a real touch. */
    fun clickId(id: Int): Boolean {
        val node = uiNode(id) ?: return false
        var n: AccessibilityNodeInfo? = node
        while (n != null) {
            if (n.isClickable && n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
            n = n.parent
        }
        return gestureOn(node, 60)
    }

    fun longClickId(id: Int): Boolean {
        val node = uiNode(id) ?: return false
        var n: AccessibilityNodeInfo? = node
        while (n != null) {
            if (n.isLongClickable &&
                n.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) return true
            n = n.parent
        }
        return gestureOn(node, 700)
    }

    /** Replace the text of field [id] (or the focused input if [id] < 0). */
    fun typeId(id: Int, text: String): Boolean {
        var node = if (id >= 0) uiNode(id) else null
        if (node == null || !node.isEditable) {
            node = (if (node != null) findEditable(node) else null)
                ?: rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                ?: findEditable(rootInActiveWindow)
                ?: return false
        }
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val args = Bundle()
        args.putCharSequence(
            AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun findEditable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.isEditable) return node
        for (i in 0 until node.childCount) {
            val hit = findEditable(node.getChild(i))
            if (hit != null) return hit
        }
        return null
    }

    /** Keyboard "enter"/search on the focused input (Android 11+). */
    fun pressEnter(): Boolean {
        if (Build.VERSION.SDK_INT < 30) return false
        val f = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            ?: return false
        return f.performAction(
            AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
    }

    /** A real touch at the node's centre — for custom views that ignore
     *  ACTION_CLICK (Compose canvases, image tiles). */
    private fun gestureOn(node: AccessibilityNodeInfo, ms: Long): Boolean {
        val r = Rect()
        node.getBoundsInScreen(r)
        if (r.isEmpty) return false
        val p = Path().apply { moveTo(r.exactCenterX(), r.exactCenterY()) }
        val g = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(p, 0, ms))
            .build()
        return dispatchGesture(g, null, null)
    }

    /** back | home | recents | notifications | quick_settings | screenshot | lock_screen */
    fun global(which: String): Boolean {
        val action = when (which) {
            "back" -> GLOBAL_ACTION_BACK
            "home" -> GLOBAL_ACTION_HOME
            "recents" -> GLOBAL_ACTION_RECENTS
            "notifications" -> GLOBAL_ACTION_NOTIFICATIONS
            "quick_settings" -> GLOBAL_ACTION_QUICK_SETTINGS
            "screenshot" -> GLOBAL_ACTION_TAKE_SCREENSHOT // API 28+
            "lock_screen" -> GLOBAL_ACTION_LOCK_SCREEN // API 28+
            else -> return false
        }
        return performGlobalAction(action)
    }
}
