from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import re

from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
from FUNCTION.JARVIS_SPEAK.speak import speak

chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
chrome_options.add_argument("--headless")  # Optional for headless

chrome_driver_path = get_chromedriver_path()
chrome_service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

# Avoid bot detection
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

driver.get("https://www.google.com")

def search_brain(text):
    try:
        search_box = driver.find_element("name","q")

        search_box.clear()
        search_box.send_keys(text)
        search_box.send_keys(Keys.RETURN)
        driver.implicitly_wait(5)

        first_result = driver.find_element(By.CSS_SELECTOR,"div.rPeykc")

        first_result_text = first_result.text
        sentences = re.split(r'(?<=[.!?])\s', first_result_text)

        filtered_sentences = [sentence for sentence in sentences if not re.search(r'https?://\s+|(\d{1,2} [A-Za-z]+ \d{10})',sentence)]

        result_text = '. '.join(filtered_sentences[:10])
        result_text = result_text.replace('Featured snippet from the web', '')
        return result_text

    except Exception as e:
        print("An error occured: ",e)

