from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import re

from FUNCTION.JARVIS_SPEAK.speak import speak

chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
chrome_options.add_argument("--headless")  # Optional for headless

chrome_driver_path = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
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





# import time
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
#
# from FUNCTION.JARVIS_SPEAK.speak import speak  # JARVIS TTS
#
# # Chrome setup
# chrome_options = Options()
# chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
# chrome_options.add_experimental_option('useAutomationExtension', False)
# chrome_options.add_argument(
#     "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# )
# # chrome_options.add_argument("--headless")  # Optional for headless
#
# chrome_driver_path = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
# chrome_service = Service(chrome_driver_path)
# driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
#
# # Avoid bot detection
# driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#
#
# def extract_short_summary(page_source):
#     soup = BeautifulSoup(page_source, "html.parser")
#     paragraphs = soup.find_all("p")
#
#     summary = ""
#     for para in paragraphs:
#         text = para.get_text().strip()
#         if len(text) > 50:
#             summary += text + " "
#         if len(summary.split()) > 50:
#             break
#
#     summary = summary.strip()
#     max_chars = 500
#
#     # Truncate at the nearest word without cutting mid-word
#     if len(summary) > max_chars:
#         words = summary.split()
#         result = ""
#         for word in words:
#             if len(result) + len(word) + 1 > max_chars:
#                 break
#             result += word + " "
#         summary = result.strip()
#
#     return summary
#
#
# def search_brain(query):
#     try:
#         driver.get("https://www.google.com/")
#         time.sleep(1)
#
#         search_box = driver.find_element(By.NAME, "q")
#         search_box.clear()
#         search_box.send_keys(query)
#         search_box.send_keys(Keys.RETURN)
#
#         WebDriverWait(driver, 10).until(
#             EC.presence_of_element_located((By.CSS_SELECTOR, 'div#search .tF2Cxc a'))
#         )
#
#         result_links = driver.find_elements(By.CSS_SELECTOR, 'div#search .tF2Cxc a')
#
#         for link in result_links:
#             try:
#                 if link.is_displayed() and link.is_enabled():
#                     url = link.get_attribute("href")
#                     if url and 'google.com' not in url:
#                         driver.get(url)
#                         time.sleep(2)
#                         summary = extract_short_summary(driver.page_source)
#                         if summary:
#                             print("🔹 Summary:\n", summary)
#                             speak(summary[:300])  # TTS limited to ~300 chars
#                         else:
#                             speak("Sorry, I couldn't extract the content.")
#                         return
#             except Exception:
#                 continue
#
#         speak("Sorry, I couldn't find any valid result.")
#
#     except Exception as e:
#         print("❌ Error:", e)
#         speak("Sorry, something went wrong.")
#
#
# search_brain("define AI")
