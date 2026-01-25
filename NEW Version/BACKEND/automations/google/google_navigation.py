# BACKEND/automations/google/google_navigation.py

def open_new_tab(driver):
    driver.execute_script(
        "window.open('https://www.google.com','_blank');"
    )
    driver.switch_to.window(driver.window_handles[-1])


def close_tab(driver):
    handles = driver.window_handles
    if len(handles) > 1:
        driver.close()
        driver.switch_to.window(handles[-1])


def next_tab(driver):
    handles = driver.window_handles
    if not handles:
        return
    i = handles.index(driver.current_window_handle)
    driver.switch_to.window(handles[(i + 1) % len(handles)])


def previous_tab(driver):
    handles = driver.window_handles
    if not handles:
        return
    i = handles.index(driver.current_window_handle)
    driver.switch_to.window(handles[(i - 1) % len(handles)])


def go_back(driver):
    driver.back()


def go_forward(driver):
    driver.forward()


def refresh(driver):
    driver.refresh()
