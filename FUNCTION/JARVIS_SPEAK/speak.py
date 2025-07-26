<<<<<<< HEAD
import time
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
from FUNCTION.LOGGER.logger import append_response  # ✅ import logger

# ─── Initialize WebDriver ─────────────────────────────────────────────
def init_driver(debug=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    chrome_service = Service(get_chromedriver_path())

    try:
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        driver.get("https://tts.5e7en.me/")
        return driver
    except Exception as e:
        print("Speak Driver init failed.")
        if debug:
            traceback.print_exc()
        raise e

# ─── Start Driver Globally ─────────────────────────────────────────────
driver = init_driver(debug=False)

# ─── Speak Function ────────────────────────────────────────────────────
def speak(text):
    try:
        if not text:
            return  # Don't proceed if text is None or empty

        print("Speaking :", text)

        # ✅ Automatically append to chat log
        append_response(bot_msg=text)

        input_box = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
        )
        input_box.click()
        input_box.send_keys(text)

        speak_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
        )
        speak_btn.click()

        # Estimate time based on length of message
        sleep_duration = max(3, min(0.2 + len(text) / 10, 50))
        time.sleep(sleep_duration)

        input_box.clear()

    except Exception as e:
        print("An error occurred in speak():", e)
        traceback.print_exc()

# import time
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
# import traceback
#
#
# def init_driver(debug=False):
#     chrome_options = Options()
#     chrome_options.add_argument("--headless")
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--log-level=3")  # Silence unnecessary logs
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#
#     chrome_service = Service(get_chromedriver_path())
#
#     try:
#         driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
#         driver.get("https://tts.5e7en.me/")
#         return driver
#     except Exception as e:
#         print("Speak Driver init failed.")
#         if debug:
#             traceback.print_exc()
#         raise e
#
# driver = init_driver(debug=False)
#
#
# def speak(text):
#     try:
#         input_box = WebDriverWait(driver, 5).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
#         )
#         input_box.click()
#         input_box.send_keys(text)
#
#         print("Speaking : ", text)
#
#         # Estimate speaking duration based on text length
#         sleep_duration = max(3, min(0.2 + len(text) / 10, 50))
#
#         speak_btn = WebDriverWait(driver, 3).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
#         )
#         speak_btn.click()
#
#         time.sleep(sleep_duration)
#         input_box.clear()
#
#     except Exception as e:
#         print("An error occurred in speak():", e)
#         traceback.print_exc()

# import time
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
#
# chrome_options = Options()
# chrome_options.add_argument("--headless")
#
# # chrome_driver_path = r'C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe'
#
# chrome_service = Service(get_chromedriver_path())
#
# driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
#
# driver.get("https://tts.5e7en.me/")
#
#
# def speak(text):
#     try:
#         element_to_click = WebDriverWait(driver, 1).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
#         )
#
#         element_to_click.click()
#
#         text_to_input = text
#         element_to_click.send_keys(text_to_input)
#         print(text_to_input)
#
#         # sleep_duration = min(0.2 + len(text) // 150, 150)
#         sleep_duration = max(3, min(0.2 + len(text) / 10, 50))
#
#         button_to_click = WebDriverWait(driver, 2).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
#         )
#
#         button_to_click.click()
#
#         time.sleep(sleep_duration)
#
#         element_to_click.clear()
#
#     except Exception as e:
#         print("An error occurred in speak : ",e)
#
=======
import os
import time
from TTS.api import TTS
import playsound

class JarvisSpeaker:
    def __init__(self, model_name="tts_models/en/ljspeech/fast_pitch", device="cpu"):
        # Initialize your offline TTS model once here
        self.tts = TTS(model_name=model_name).to(device)

    def speak(self, text="Hello", file_path=None):
        if not text:
            return  # Do nothing if text is empty or None
        print("Speaking :", text)

        # Use unique filename if not provided
        if file_path is None:
            filename = f"output_{int(time.time() * 1000)}.wav"
            file_path = os.path.join("outputs", filename)

        # Ensure output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        try:
            # Generate and save audio locally
            self.tts.tts_to_file(text=text, file_path=file_path)
        except PermissionError as e:
            print(f"PermissionError writing TTS file: {e}")
            raise

        # Convert Windows-style path to forward slashes for playsound compatibility
        abs_path = os.path.abspath(file_path).replace("\\", "/")

        # Play the saved audio file
        playsound.playsound(abs_path)
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)
