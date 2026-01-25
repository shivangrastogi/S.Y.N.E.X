# BACKEND/automations/google/google_scroll.py

def scroll_down(driver, pixels=800):
    driver.execute_script("window.scrollBy(0, arguments[0]);", pixels)


def scroll_up(driver, pixels=800):
    driver.execute_script("window.scrollBy(0, -arguments[0]);", pixels)


def scroll_to_top(driver):
    driver.execute_script("window.scrollTo(0, 0);")


def scroll_to_bottom(driver):
    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);"
    )
