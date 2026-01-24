#Working Code
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import urllib.parse

from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path


def search_google(query):
    chrome_driver_path = get_chromedriver_path()  # Replace this with your actual path

    # Configure browser
    options = Options()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")  # Optional: run in headless mode
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)

    try:
        # Format search URL
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        driver.get(url)

        wait = WebDriverWait(driver, 10)

        # Wait and get the first result title (more robust with text-based XPath)
        first_result = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'h3'
        )))

        result_text = first_result.text
        result_link = first_result.find_element(By.XPATH, "..").get_attribute("href")

        print("Top result title:", result_text)
        print("Top result link:", result_link)

        return result_text, result_link

    except Exception as e:
        print("An error occurred:", e)
        return None, None

    finally:
        time.sleep(2)
        driver.quit()

# ✅ Example usage:
if __name__ == "__main__":
    query = "what is anubhav chaturvedi"
    title, link = search_google(query)


# import time, re
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
#
# from sumy.parsers.plaintext import PlaintextParser
# from sumy.nlp.tokenizers import Tokenizer
# from sumy.summarizers.lsa import LsaSummarizer
# from sumy.summarizers.text_rank import TextRankSummarizer
#
# from FUNCTION.ChromeWebdriverLocation.utils import get_chromedriver_path
#
# # CONFIG
# CHROMEDRIVER_PATH = get_chromedriver_path()
#
# def create_driver():
#     options = Options()
#     options.add_argument("--disable-blink-features=AutomationControlled")
#     options.add_experimental_option("excludeSwitches", ["enable-automation"])
#     options.add_experimental_option('useAutomationExtension', False)
#     options.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
#     )
#     options.add_argument("--headless")  # Optional
#     service = Service(CHROMEDRIVER_PATH)
#     driver = webdriver.Chrome(service=service, options=options)
#     driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#     return driver
#
# def search_and_extract(driver, query):
#     try:
#         driver.get("https://www.google.com/")
#         time.sleep(1)
#
#         search_box = driver.find_element(By.NAME, "q")
#         search_box.clear()
#         for char in query:
#             search_box.send_keys(char)
#             time.sleep(0.06)
#         search_box.send_keys(Keys.RETURN)
#
#         # Wait for search results
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
#                     if url and 'google.com' not in url and 'javascript:void(0)' not in url:
#                         driver.get(url)
#                         time.sleep(2)
#                         return extract_text_from_page(driver.page_source)
#             except Exception as e:
#                 print("🔸 Skipped a result due to error:", e)
#                 continue
#
#         print("❌ No valid link found.")
#         return None
#
#     except Exception as e:
#         print("❌ Error during search:", str(e))
#         import traceback
#         traceback.print_exc()
#         return None
#
#
# def extract_text_from_page(html):
#     soup = BeautifulSoup(html, "html.parser")
#     paragraphs = [p.get_text() for p in soup.find_all("p")]
#     full_text = ' '.join(paragraphs)
#     cleaned = re.sub(r'\s+', ' ', full_text).strip()
#     return cleaned
#
# def summarize_text(text, sentence_count=5):
#     if not text:
#         return "No content to summarize."
#     parser = PlaintextParser.from_string(text, Tokenizer("english"))
#     summarizer = TextRankSummarizer()
#     summary = summarizer(parser.document, sentence_count)
#     return ' '.join(str(sentence) for sentence in summary)
#
# def deep_search(query):
#     driver = create_driver()
#     try:
#         extracted_text = search_and_extract(driver, query)
#         if extracted_text:
#             summary = summarize_text(extracted_text)
#             return summary
#         else:
#             return "No content extracted."
#     finally:
#         driver.quit()
#




# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import time
#
# chrome_driver_path = r"D:\Study things\jarvis files\JARVIS\Just-A-Rather-Very-Intelligent-System-main\chromedriver.exe"  # Replace this with your chromedriver path
#
# options = Options()
# # options.add_argument("--headless")  # UNCOMMENT ONLY after it's working
# options.add_argument("--start-maximized")
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)
# options.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# )
#
# driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)
# driver.get("https://www.google.com/search?q=what+is+anubhav+chaturvedi")
#
# try:
#     # Wait for the h3 inside search result
#     wait = WebDriverWait(driver, 10)
#
#     # Instead of full class match, use partial match with XPath
#     result = wait.until(EC.presence_of_element_located((
#         By.XPATH, "//h3[contains(text(),'Anubhav Chaturvedi')]"
#     )))
#
#     print("Found result:", result.text)
#
# except Exception as e:
#     print("An error occurred:", e)
#
# finally:
#     time.sleep(3)
#     driver.quit()