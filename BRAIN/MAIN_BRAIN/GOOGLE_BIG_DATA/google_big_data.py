import time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer

# CONFIG
CHROMEDRIVER_PATH = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"

def create_driver():
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_argument("--headless")  # Optional
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def search_and_extract(driver, query):
    try:
        driver.get("https://www.google.com/")
        time.sleep(1)

        search_box = driver.find_element(By.NAME, "q")
        search_box.clear()
        for char in query:
            search_box.send_keys(char)
            time.sleep(0.06)
        search_box.send_keys(Keys.RETURN)

        # Wait for search results
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div#search .tF2Cxc a'))
        )

        result_links = driver.find_elements(By.CSS_SELECTOR, 'div#search .tF2Cxc a')

        for link in result_links:
            try:
                if link.is_displayed() and link.is_enabled():
                    url = link.get_attribute("href")
                    if url and 'google.com' not in url and 'javascript:void(0)' not in url:
                        driver.get(url)
                        time.sleep(2)
                        return extract_text_from_page(driver.page_source)
            except Exception as e:
                print("🔸 Skipped a result due to error:", e)
                continue

        print("❌ No valid link found.")
        return None

    except Exception as e:
        print("❌ Error during search:", str(e))
        import traceback
        traceback.print_exc()
        return None


def extract_text_from_page(html):
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [p.get_text() for p in soup.find_all("p")]
    full_text = ' '.join(paragraphs)
    cleaned = re.sub(r'\s+', ' ', full_text).strip()
    return cleaned

def summarize_text(text, sentence_count=5):
    if not text:
        return "No content to summarize."
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, sentence_count)
    return ' '.join(str(sentence) for sentence in summary)

def deep_search(query):
    driver = create_driver()
    try:
        extracted_text = search_and_extract(driver, query)
        if extracted_text:
            summary = summarize_text(extracted_text)
            return summary
        else:
            return "No content extracted."
    finally:
        driver.quit()


