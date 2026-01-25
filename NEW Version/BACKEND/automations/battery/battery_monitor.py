# BACKEND/automations/battery/battery_monitor.py
import psutil
import time
import threading
import traceback
from dataclasses import dataclass

from BACKEND.core.brain.state_manager import AudioState


@dataclass
class BatteryMonitorConfig:
    critical_threshold: int = 10
    low_threshold: int = 30
    full_threshold: int = 100
    plug_cooldown: int = 180
    level_cooldown: int = 300
    idle_only: bool = True  # announce only when idle; queue otherwise
    max_pending: int = 5


class BatteryMonitor:
    """
    Background battery monitoring service
    Runs independently of user commands
    """

    def __init__(self, speaker, interval=60, config: BatteryMonitorConfig | None = None, settings=None):
        self.speaker = speaker
        self.interval = interval
        self.config = config or BatteryMonitorConfig()
        self.settings = settings  # Optional: use external settings if provided
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()

        self._state_manager = self._infer_state_manager(speaker)

        self._last_level = None
        self._last_plugged = None
        self._last_percent = None
        self._no_battery_logged = False
        self._last_alert_time = {}
        self._pending_announcements = []

    def start(self):
        # Check if monitoring is enabled in settings
        if self.settings:
            cfg = self.settings.get_config()
            if not cfg.enable_monitoring:
                if cfg.debug:
                    print("[Battery Monitor] Monitoring disabled in settings; not starting.")
                return
        
        if self._running and self._thread and self._thread.is_alive():
            return  # prevent duplicate threads

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def _infer_state_manager(self, speaker):
        # Try common locations to get state; stay resilient if missing
        if hasattr(speaker, "state_manager"):
            return speaker.state_manager
        if hasattr(speaker, "tts") and hasattr(speaker.tts, "state_manager"):
            return speaker.tts.state_manager
        return None

    def _is_idle(self) -> bool:
        if not self.config.idle_only:
            return True
        if not self._state_manager:
            return True
        return self._state_manager.is_idle()

    def _speak_or_queue(self, message: str):
        # Speak immediately if idle; otherwise queue for later flush
        if self._is_idle():
            self._safe_speak(message)
            return

        if len(self._pending_announcements) >= self.config.max_pending:
            # Drop oldest to keep list bounded
            self._pending_announcements.pop(0)
        self._pending_announcements.append(message)

    def _flush_pending(self):
        if not self._pending_announcements:
            return
        if not self._is_idle():
            return
        # Deliver queued messages in order
        while self._pending_announcements:
            msg = self._pending_announcements.pop(0)
            self._safe_speak(msg)

    def _safe_speak(self, message: str):
        """Speak defensively, honoring speaking state if available."""
        try:
            if self._state_manager and self._state_manager.state == AudioState.SPEAKING:
                return
            self.speaker.speak(message)
        except Exception:
            pass

    def _can_alert(self, key: str, cooldown: int | None = None) -> bool:
        now = time.time()
        last = self._last_alert_time.get(key, 0)
        period = cooldown if cooldown is not None else self.config.level_cooldown
        if now - last >= period:
            self._last_alert_time[key] = now
            return True
        return False

    def _run(self):
        while self._running and not self._stop_event.is_set():
            try:
                battery = psutil.sensors_battery()
                if not battery:
                    if not self._no_battery_logged:
                        print("[Battery] No battery detected; stopping monitor.")
                        self._no_battery_logged = True
                    self._running = False
                    self._stop_event.set()
                    break

                percent = int(battery.percent)
                plugged = battery.power_plugged

                # 🔌 Plug / Unplug detection
                if self._last_plugged is None:
                    self._last_plugged = plugged

                elif plugged != self._last_plugged:
                    if self._can_alert("plug", cooldown=self.config.plug_cooldown):
                        self._speak_or_queue(
                            "Charger connected." if plugged else "Charger disconnected."
                        )
                    self._last_plugged = plugged

                # 🔋 Battery level alerts
                if percent <= self.config.critical_threshold and self._last_level != "critical":
                    if self._can_alert("critical"):
                        self._speak_or_queue(
                            "Battery is critically low. Please connect the charger."
                        )
                    self._last_level = "critical"

                elif percent <= self.config.low_threshold and self._last_level != "low":
                    if self._can_alert("low"):
                        self._speak_or_queue(
                            f"Battery is at {percent} percent. Consider charging soon."
                        )
                    self._last_level = "low"

                elif percent >= self.config.full_threshold and self._last_level != "full":
                    if self._can_alert("full"):
                        self._speak_or_queue(
                            "Battery is fully charged. You may unplug the charger."
                        )
                    self._last_level = "full"

                elif self.config.low_threshold < percent < self.config.full_threshold:
                    self._last_level = None

                self._last_percent = percent
                self._flush_pending()

            except Exception:
                traceback.print_exc()

            # Use settings interval if available, otherwise use config interval
            interval = self.interval
            if self.settings:
                interval = self.settings.get_config().monitor_interval
            self._stop_event.wait(interval)
