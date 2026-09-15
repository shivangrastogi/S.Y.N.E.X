# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/event_bridge.py
from PyQt5.QtCore import QObject, pyqtSignal
from aeris.core.event_bus import event_bus

class EventBridge(QObject):
    """
    Phase 8: Safely bridges A.E.R.I.S background threads (Vosk, Execution Engine) 
    to the Qt Main Event Loop.
    
    Qt Widgets MUST ONLY be modified from the main thread.
    This bridge catches `event_bus` callbacks (executed on worker threads) 
    and emits `pyqtSignal` events, which Qt safely queues onto the main thread.
    """
    
    # Typed Signals for Qt
    state_changed = pyqtSignal(str)
    text_heard = pyqtSignal(str)
    partial_text_heard = pyqtSignal(str)
    task_started = pyqtSignal(dict)
    task_completed = pyqtSignal(dict)
    task_cancelled = pyqtSignal(str)
    safe_mode_activated = pyqtSignal(dict)
    manual_listen_trigger = pyqtSignal()
    audio_level = pyqtSignal(float)
    
    # Laptop UI Specific
    gesture_status = pyqtSignal(bool, str, float)
    gesture_frame = pyqtSignal(object)
    gesture_event = pyqtSignal(str)
    user_profile = pyqtSignal(dict)
    lock_state = pyqtSignal(bool)
    settings_received = pyqtSignal(dict)
    mobile_notification = pyqtSignal(str, str, str) # app, title, text
    device_status = pyqtSignal(bool, str, str, str) # connected, name, id, ip
    incoming_call = pyqtSignal(str, str, str)      # caller, number, status
    google_status = pyqtSignal(bool, str)          # connected, email
    voice_list = pyqtSignal(list)
    download_progress = pyqtSignal(str, int)       # model_name, progress
    image_started = pyqtSignal(str)                # prompt
    image_finished = pyqtSignal(object)            # metadata
    image_progress = pyqtSignal(int, float)        # percentage, eta
    system_metrics = pyqtSignal(dict)              # cpu, mem, etc.

    def __init__(self):
        super().__init__()
        
        # Subscribe to Core Foundation Events
        event_bus.subscribe("system.state_changed", self._on_state_changed)
        event_bus.subscribe("voice.text_heard", self._on_text_heard)
        event_bus.subscribe("voice.partial_text", self._on_partial_text)
        event_bus.subscribe("voice.audio_level", self._on_audio_level)
        event_bus.subscribe("execution.task_started", self._on_task_started)
        event_bus.subscribe("execution.task_completed", self._on_task_completed)
        event_bus.subscribe("execution.cancelled", self._on_task_cancelled)
        event_bus.subscribe("system.safe_mode_activated", self._on_safe_mode)
        event_bus.subscribe("voice.manual_listen_trigger", lambda p: self.manual_listen_trigger.emit())
        
        # Laptop UI Subscriptions
        event_bus.subscribe("gestures.status", lambda p: self.gesture_status.emit(p.get("active", False), p.get("gesture", "NONE"), p.get("fps", 0.0)))
        event_bus.subscribe("gestures.frame", lambda p: self.gesture_frame.emit(p.get("frame")))
        event_bus.subscribe("gestures.event", lambda p: self.gesture_event.emit(p.get("gesture", "NONE")))
        event_bus.subscribe("system.user_profile", lambda p: self.user_profile.emit(p))
        event_bus.subscribe("system.lock_state", lambda p: self.lock_state.emit(p.get("locked", False)))
        event_bus.subscribe("system.settings", lambda p: self.settings_received.emit(p))
        event_bus.subscribe("mobile.notification", lambda p: self.mobile_notification.emit(p.get("app", ""), p.get("title", ""), p.get("text", "")))
        event_bus.subscribe("mobile.device_status", lambda p: self.device_status.emit(p.get("connected", False), p.get("name", ""), p.get("id", ""), p.get("ip", "")))
        event_bus.subscribe("mobile.incoming_call", lambda p: self.incoming_call.emit(p.get("caller", ""), p.get("number", ""), p.get("status", "")))
        event_bus.subscribe("system.google_status", lambda p: self.google_status.emit(p.get("connected", False), p.get("email", "")))
        event_bus.subscribe("voice.list", lambda p: self.voice_list.emit(p))
        event_bus.subscribe("voice.download_progress", lambda p: self.download_progress.emit(p.get("model", ""), p.get("progress", 0)))
        event_bus.subscribe("image.started", lambda p: self.image_started.emit(p.get("prompt", "")))
        event_bus.subscribe("image.finished", lambda p: self.image_finished.emit(p.get("metadata", {})))
        event_bus.subscribe("image.progress", lambda p: self.image_progress.emit(p.get("percentage", 0), p.get("eta", 0.0)))
        event_bus.subscribe("system.metrics", lambda p: self.system_metrics.emit(p))

    # --- Router Callbacks (Running on Worker Threads) ---

    def _on_state_changed(self, payload: dict):
        new_state = payload.get("new_state", "IDLE")
        self.state_changed.emit(new_state)

    def _on_text_heard(self, payload: dict):
        text = payload.get("text", "")
        self.text_heard.emit(text)
        
    def _on_partial_text(self, payload: dict):
        text = payload.get("text", "")
        self.partial_text_heard.emit(text)
        
    def _on_audio_level(self, payload: dict):
        level = payload.get("level", 0.0)
        self.audio_level.emit(level)
        
    def _on_task_started(self, payload: dict):
        self.task_started.emit(payload)
        
    def _on_task_completed(self, payload: dict):
        self.task_completed.emit(payload)

    def _on_task_cancelled(self, payload: dict):
        self.task_cancelled.emit("Cancelled")
        
    def _on_safe_mode(self, payload: dict):
        self.safe_mode_activated.emit(payload)

# Global bridge singleton
ui_bridge = EventBridge()
