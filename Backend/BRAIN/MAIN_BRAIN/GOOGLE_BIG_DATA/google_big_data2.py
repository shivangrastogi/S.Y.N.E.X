# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.support.wait import WebDriverWait
# import re
#
# # Sumy Libraries
# from sumy.parsers.plaintext import PlaintextParser
# from sumy.nlp.tokenizers import Tokenizer
# from sumy.summarizers.lsa import LsaSummarizer
#
# # Selenium setup
# options = Options()
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)
# options.add_argument(
#     "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# )
# # options.add_argument("--headless")  # Uncomment to run headless
#
# CHROMEDRIVER_PATH = r"C:\Users\bosss\Desktop\JARVIS\DATA\JARVIS_DRIVER\chromedriver.exe"
# service = Service(CHROMEDRIVER_PATH)
# driver = webdriver.Chrome(service=service, options=options)
# driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#
# # -------------------- SEARCH AND EXTRACT FUNCTION --------------------
# def search_and_extract(text):
#     try:
#         driver.get("https://www.google.com")
#         search_box = driver.find_element("name", "q")
#         search_box.send_keys(text)
#         search_box.send_keys(Keys.RETURN)
#
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search .tF2Cxc a")))
#
#         # Get first result link
#         first_result = driver.find_element(By.CSS_SELECTOR, 'div#search .tF2Cxc a')
#         first_result_link = first_result.get_attribute('href')
#         driver.get(first_result_link)
#
#         # Extract paragraph text
#         soup = BeautifulSoup(driver.page_source, "html.parser")
#         paragraph_text = ' '.join([p.get_text() for p in soup.find_all('p')])
#
#         # Clean and split into sentences
#         sentences = re.split(r'(?<=[.!?])\s+', paragraph_text)
#         result_text = ' '.join(sentences[:10])
#         return result_text
#
#     except Exception as e:
#         print("An error occurred during search:", e)
#         return ""
#
# # -------------------- SUMMARIZATION FUNCTION --------------------
# def summarize_text(text, sentence_count=5):
#     parser = PlaintextParser.from_string(text, Tokenizer("english"))
#     summarizer = LsaSummarizer()
#     summary = summarizer(parser.document, sentence_count)
#     return ' '.join(str(sentence) for sentence in summary)
#
# # -------------------- MAIN LOOP --------------------
# while True:
#     x = input("Enter a search query (or 'exit' to end): ")
#     if x.lower() == "exit":
#         break
#
#     extracted_text = search_and_extract(x)
#     print("\n--- Extracted Text ---\n", extracted_text)
#
#     print("\n--- Summary ---")
#     if extracted_text.strip():
#         summary_output = summarize_text(extracted_text)
#         print(summary_output)
#     else:
#         print("No content to summarize.")
#
# driver.quit()
