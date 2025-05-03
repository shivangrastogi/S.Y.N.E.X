from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
import re

# Sumy Libraries
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

# Selenium setup
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
# options.add_argument("--headless")  # Uncomment to run headless

CHROMEDRIVER_PATH = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# -------------------- SEARCH AND EXTRACT FUNCTION --------------------
def search_and_extract(text):
    try:
        driver.get("https://www.google.com")
        search_box = driver.find_element("name", "q")
        search_box.send_keys(text)
        search_box.send_keys(Keys.RETURN)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search .tF2Cxc a")))

        # Get first result link
        first_result = driver.find_element(By.CSS_SELECTOR, 'div#search .tF2Cxc a')
        first_result_link = first_result.get_attribute('href')
        driver.get(first_result_link)

        # Extract paragraph text
        soup = BeautifulSoup(driver.page_source, "html.parser")
        paragraph_text = ' '.join([p.get_text() for p in soup.find_all('p')])

        # Clean and split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', paragraph_text)
        result_text = ' '.join(sentences[:10])
        return result_text

    except Exception as e:
        print("An error occurred during search:", e)
        return ""

# -------------------- SUMMARIZATION FUNCTION --------------------
def summarize_text(text, sentence_count=5):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, sentence_count)
    return ' '.join(str(sentence) for sentence in summary)

# -------------------- MAIN LOOP --------------------
while True:
    x = input("Enter a search query (or 'exit' to end): ")
    if x.lower() == "exit":
        break

    extracted_text = search_and_extract(x)
    print("\n--- Extracted Text ---\n", extracted_text)

    print("\n--- Summary ---")
    if extracted_text.strip():
        summary_output = summarize_text(extracted_text)
        print(summary_output)
    else:
        print("No content to summarize.")

driver.quit()




# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# import re
#
# from selenium.webdriver.support.wait import WebDriverWait
#
# options = Options()
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)
# options.add_argument(
#     "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# )
# # options.add_argument("--headless")  # Optional
# CHROMEDRIVER_PATH = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
# service = Service(CHROMEDRIVER_PATH)
# driver = webdriver.Chrome(service=service, options=options)
# driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#
#
# def search_and_extract(text):
#     try:
#         driver.get("https://www.google.com")
#
#         search_box = driver.find_element("name", "q")
#
#         search_query = text
#         search_box.send_keys(search_query)
#         search_box.send_keys(Keys.RETURN)
#
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
#
#         # Select the first link from the search results
#         first_result = driver.find_element(By.CSS_SELECTOR, 'div#search .tF2Cxc a')
#         first_result_link = first_result.get_attribute('href')
#         driver.get(first_result_link)
#
#         webpage_content = driver.page_source
#
#         soup = BeautifulSoup(webpage_content, "html.parser")
#
#         webpage_text = ' '.join([p.get_text() for p in soup.find_all('p')])
#
#         sentences = re.split(r'(?<=[.!?])\s', webpage_text)
#         result_text = ' '.join(sentences[:9])
#         return result_text
#
#     except Exception as e:
#         print("An error occurred:", e)
#
#
#
# from sumy.parsers.plaintext import PlaintextParser
# from sumy.nlp.tokenizers import Tokenizer
# from sumy.summarizers.lsa import LsaSummarizer
#
# def summarize_text(text, sentence_count=5):
#     parser = PlaintextParser.from_string(text, Tokenizer("english"))
#     summarizer = LsaSummarizer()
#     summary = summarizer(parser.document, sentence_count)
#     return ' '.join([str(sentence) for sentence in summary])
#
# def summary(text):
#     text_to_summarize = text
#     summary_results = summarize_text(text_to_summarize)
#     print(summary_results)
#
#
# while True:
#     x = input("enter a search query (or 'exit' to end): ")
#     if x.lower() == "exit":
#         break
#     y = search_and_extract(x)
#     print(y)
#     print("###########################################")
#     z = summary(y)
#     print(z)
#
# driver.quit()

# def deep_search(text):
#     x = text
#     y = search_and_extract(x)
#     print(y)
#     print("#################")
#     z = summary(y)
#     print(z)
#     driver.quit()
#
# deep_search("What is machine learning")





# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# import re
#
# from selenium.webdriver.support.wait import WebDriverWait
#
# options = Options()
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)
# options.add_argument(
#     "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# )
# # options.add_argument("--headless")  # Optional
# CHROMEDRIVER_PATH = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
# service = Service(CHROMEDRIVER_PATH)
# driver = webdriver.Chrome(service=service, options=options)
# driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#
#
# def search_and_extract(text):
#     try:
#         driver.get("https://www.google.com")
#
#         search_box = driver.find_element("name", "q")
#
#         search_query = text
#         search_box.send_keys(search_query)
#         search_box.send_keys(Keys.RETURN)
#
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
#
#         first_result = driver.find_element(By.CSS_SELECTOR,'div.g')
#
#         first_result_link = first_result.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
#         driver.get(first_result_link)
#
#         webpage_content = driver.page_source
#
#         soup = BeautifulSoup(webpage_content, "html.parser")
#
#         webpage_text = ' '.join([p.get_text() for p in soup.find_all('p')])
#
#         sentences = re.split(r'(?<=[.!?])\s', webpage_text)
#         result_text = ' '.join(sentences[:9])
#         return result_text
#
#     except Exception as e:
#         print("An error occured : ",e)
#
#     except Exception as e:
#         print("An error occured : ",e)
#
#
# from sumy.parsers.plaintext import PlaintextParser
# from sumy.nlp.tokenizers import Tokenizer
# from sumy.summarizers.lsa import LsaSummarizer
#
# def summarize_text(text,sentence_count=5):
#     parser = PlaintextParser.from_string(text,Tokenizer("english"))
#     summarizer = LsaSummarizer()
#     summary = summarizer(parser.document, sentence_count)
#     return ' '.join([str(sentence) for sentence in summary])
#
# def summary(text):
#     summary_results = summarize_text(text)
#     print(summary_results)
#
# def deep_search(text):
#     x = text
#     y = search_and_extract(x)
#     print(y)
#     print("#################")
#     z = summary(y)
#     print(z)
#     driver.quit()
#
# deep_search("What is machine learning")