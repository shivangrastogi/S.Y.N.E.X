import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
import traceback


def init_driver(debug=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")  # Silence unnecessary logs
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

driver = init_driver(debug=False)


def speak(text):
    try:
        input_box = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
        )
        input_box.click()
        input_box.send_keys(text)

        print("Speaking : ", text)

        # Estimate speaking duration based on text length
        sleep_duration = max(3, min(0.2 + len(text) / 10, 50))

        speak_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
        )
        speak_btn.click()

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
