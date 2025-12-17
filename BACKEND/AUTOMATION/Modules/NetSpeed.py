# BACKEND/AUTOMATION/Modules/NetSpeed.py

import requests
import time
import statistics


URL = "https://speed.cloudflare.com/__down?bytes=200000000"
CHUNK_SIZE = 1024 * 128  # 128 KB
TIMEOUT = 15


def _single_measurement(duration=3.0, warmup_bytes=5_000_000):
    """
    Runs ONE stabilized download measurement.
    Returns Mbps or None.
    """
    try:
        response = requests.get(URL, stream=True, timeout=TIMEOUT)
        response.raise_for_status()

        total_bytes = 0
        measured_bytes = 0
        measuring = False
        start = time.perf_counter()
        measure_start = None

        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue

            total_bytes += len(chunk)
            now = time.perf_counter()

            # ---- WARM-UP: wait for bandwidth to ramp ----
            if not measuring:
                if total_bytes >= warmup_bytes:
                    measuring = True
                    measure_start = now
                continue

            # ---- MEASUREMENT ----
            measured_bytes += len(chunk)

            if now - measure_start >= duration:
                break

        if not measure_start or measured_bytes == 0:
            return None

        elapsed = time.perf_counter() - measure_start
        if elapsed <= 0:
            return None

        return (measured_bytes * 8) / elapsed / 1_000_000  # Mbps

    except Exception:
        return None


def check_download_speed(samples=5):
    """
    Robust speed test using multiple stabilized samples.
    Returns median Mbps.
    """

    print("🌐 Running stabilized internet speed test...")

    results = []

    for i in range(samples):
        speed = _single_measurement()
        if speed:
            results.append(speed)
        time.sleep(0.2)  # slight pause between runs

    if len(results) < 3:
        return None

    # ---- Robust statistics ----
    median_speed = statistics.median(results)

    return int(round(median_speed, 2))


# --- Standalone Test ---
if __name__ == "__main__":
    print("Starting Speed Test...")
    speed = check_download_speed()

    if speed is not None:
        print(f"FINAL RESULT: {speed} Mbps")
    else:
        print("Test failed. Check internet connection.")
