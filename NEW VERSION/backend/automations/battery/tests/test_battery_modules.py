import time
import types
import unittest
from unittest.mock import patch

from BACKEND.automations.battery.battery_monitor import BatteryMonitor, BatteryMonitorConfig
from BACKEND.automations.battery.battery_status import speak_battery_percentage
from BACKEND.automations.battery.battery_plug import speak_plug_status
from BACKEND.automations.battery.battery_controller import BatteryController


class FakeStateManager:
    def __init__(self):
        self._idle = True
        self.state = types.SimpleNamespace(value="idle")

    def is_idle(self):
        return self._idle

    def set_idle(self, v: bool):
        self._idle = v


class FakeSpeaker:
    def __init__(self):
        self.messages = []
        self.tts = types.SimpleNamespace(state_manager=FakeStateManager())
        # Also expose state_manager at top-level for monitor inference
        self.state_manager = self.tts.state_manager

    def speak(self, text: str):
        self.messages.append(text)


class BatteryInfo:
    def __init__(self, percent: int, power_plugged: bool):
        self.percent = percent
        self.power_plugged = power_plugged


class BatteryModulesTest(unittest.TestCase):
    def setUp(self):
        self.speaker = FakeSpeaker()
        # Tight intervals and cooldowns for fast tests
        self.cfg = BatteryMonitorConfig(
            critical_threshold=10,
            low_threshold=30,
            full_threshold=100,
            plug_cooldown=0,
            level_cooldown=0,
            idle_only=True,
            max_pending=5,
        )
        self.monitor = BatteryMonitor(self.speaker, interval=0.05, config=self.cfg)

    def tearDown(self):
        try:
            self.monitor.stop()
        except Exception:
            pass

    def _start_with_battery(self, percent=50, plugged=False):
        current = BatteryInfo(percent, plugged)
        def fake_sensors_battery():
            return current
        self.current_battery = current
        self.patcher = patch("psutil.sensors_battery", fake_sensors_battery)
        self.patcher.start()
        self.monitor.start()
        return current

    def _stop_patch(self):
        try:
            self.patcher.stop()
        except Exception:
            pass

    def test_plug_unplug_idle_announces(self):
        cur = self._start_with_battery(percent=50, plugged=False)
        time.sleep(0.1)
        cur.power_plugged = True
        time.sleep(0.15)
        cur.power_plugged = False
        time.sleep(0.15)
        self.monitor.stop()
        self._stop_patch()
        # Expect both connect and disconnect announcements
        joined = " ".join(self.speaker.messages)
        self.assertIn("Charger connected.", joined)
        self.assertIn("Charger disconnected.", joined)

    def test_low_and_critical_alerts(self):
        cur = self._start_with_battery(percent=35, plugged=False)
        time.sleep(0.1)
        # low threshold
        cur.percent = 30
        time.sleep(0.15)
        # critical
        cur.percent = 10
        time.sleep(0.15)
        self.monitor.stop()
        self._stop_patch()
        joined = " ".join(self.speaker.messages)
        self.assertIn("Battery is at 30 percent", joined)
        self.assertIn("critically low", joined)

    def test_full_alert(self):
        cur = self._start_with_battery(percent=99, plugged=True)
        time.sleep(0.1)
        cur.percent = 100
        time.sleep(0.15)
        self.monitor.stop()
        self._stop_patch()
        joined = " ".join(self.speaker.messages)
        self.assertIn("fully charged", joined)

    def test_queue_when_busy_and_flush_on_idle(self):
        # Start busy (not idle)
        self.speaker.state_manager.set_idle(False)
        cur = self._start_with_battery(percent=25, plugged=False)
        time.sleep(0.1)
        cur.power_plugged = True
        time.sleep(0.15)
        # Still busy, should queue, not speak yet
        self.assertEqual(len(self.speaker.messages), 0)
        # Become idle and allow flush
        self.speaker.state_manager.set_idle(True)
        time.sleep(0.2)
        self.monitor.stop()
        self._stop_patch()
        joined = " ".join(self.speaker.messages)
        self.assertIn("connected", joined)
        self.assertTrue(len(self.speaker.messages) >= 1)

    def test_monitor_stops_promptly(self):
        cur = self._start_with_battery(percent=50, plugged=False)
        time.sleep(0.1)
        start = time.time()
        self.monitor.stop()
        self._stop_patch()
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0)

    def test_simple_intents_return_and_speak(self):
        # Patch psutil for deterministic outputs
        info = BatteryInfo(42, True)
        with patch("psutil.sensors_battery", lambda: info):
            msg1 = speak_battery_percentage(self.speaker)
            msg2 = speak_plug_status(self.speaker)
        self.assertIn("42", msg1)
        self.assertIn("plugged", msg2)
        # Also controller routing
        ctrl = BatteryController(self.speaker)
        with patch("psutil.sensors_battery", lambda: info):
            self.assertIn("42", ctrl.handle("check_battery_percentage"))
            self.assertIn("plugged", ctrl.handle("check_battery_plug"))


if __name__ == "__main__":
    unittest.main()
