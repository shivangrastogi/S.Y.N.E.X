import psutil
import time
import threading
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SystemMonitor:
    def __init__(self, tts_engine):
        self.tts = tts_engine
        self.is_monitoring = True
        self.battery_threshold = 20
        self.cpu_threshold = 90
        
        # Tracking states to avoid repetitive alerts
        self.last_battery_alert = 0
        self.last_cpu_alert = 0

    def start(self):
        """Starts the monitoring thread."""
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        print("Background System Monitoring started.")

    def monitor_loop(self):
        while self.is_monitoring:
            try:
                # 1. Check Battery
                battery = psutil.sensors_battery()
                if battery:
                    percent = battery.percent
                    power_plugged = battery.power_plugged
                    
                    if percent <= self.battery_threshold and not power_plugged:
                        current_time = time.time()
                        # Alert every 10 minutes
                        if current_time - self.last_battery_alert > 600:
                            self.tts.speak(f"Sir, battery {percent} percent hai. Please charger connect kijiye.")
                            self.last_battery_alert = current_time

                # 2. Check CPU Usage
                cpu_usage = psutil.cpu_percent(interval=1)
                if cpu_usage > self.cpu_threshold:
                    current_time = time.time()
                    # Alert every 5 minutes
                    if current_time - self.last_cpu_alert > 300:
                        self.tts.speak("Warning sir, CPU usage bohot high hai. Laptop garam ho sakta hai.")
                        self.last_cpu_alert = current_time

                # Sleep to prevent high CPU usage from the monitor itself
                time.sleep(30)

            except Exception as e:
                print(f"Monitor Error: {str(e)}")
                time.sleep(10)

    def stop(self):
        self.is_monitoring = False

if __name__ == "__main__":
    # Test simulation
    from core.tts import TTS
    tts = TTS()
    monitor = SystemMonitor(tts)
    # We run it manually for testing
    print("Testing System Monitor... (Simulating 1 cycle)")
    monitor.monitor_loop()
