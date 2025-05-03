import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_options = Options()
chrome_options.add_argument("--headless")

chrome_driver_path = r'C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe'

chrome_service = Service(chrome_driver_path)

driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

driver.get("https://tts.5e7en.me/")


def speak(text):
    try:
        element_to_click = WebDriverWait(driver, 1).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
        )

        element_to_click.click()

        text_to_input = text
        element_to_click.send_keys(text_to_input)
        print(text_to_input)

        # sleep_duration = min(0.2 + len(text) // 150, 150)
        sleep_duration = max(3, min(0.2 + len(text) / 10, 50))

        button_to_click = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
        )

        button_to_click.click()

        time.sleep(sleep_duration)

        element_to_click.clear()

    except Exception as e:
        print("An error occurred : ",e)


# from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
# from selenium.webdriver.common.alert import Alert
# import time
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
#
# chrome_options = Options()
# chrome_options.add_argument("--headless")
#
# chrome_driver_path = r'C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe'
#
# chrome_service = Service(chrome_driver_path)
#
# driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
#
# driver.get("https://tts.5e7en.me/")
# def speak(text):
#     if not text.strip():
#         print("No text provided to speak. Skipping TTS.")
#         return
#
#     try:
#         element_to_click = WebDriverWait(driver, 3).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="text"]'))
#         )
#
#         element_to_click.click()
#         element_to_click.send_keys(text)
#         print(text)
#
#         sleep_duration = max(3, min(0.2 + len(text) / 10, 50))
#
#         button_to_click = WebDriverWait(driver, 3).until(
#             EC.element_to_be_clickable((By.XPATH, '//*[@id="button"]'))
#         )
#         button_to_click.click()
#
#         time.sleep(sleep_duration)
#
#     except UnexpectedAlertPresentException:
#         try:
#             alert = Alert(driver)
#             print(f"Handling unexpected alert: {alert.text}")
#             alert.dismiss()
#         except NoAlertPresentException:
#             pass
#
#     finally:
#         # Try to clear the input only if it's safe to do so
#         try:
#             element_to_click = driver.find_element(By.XPATH, '//*[@id="text"]')
#             element_to_click.clear()
#         except Exception as e:
#             print("Unable to clear input field:", e)
#
