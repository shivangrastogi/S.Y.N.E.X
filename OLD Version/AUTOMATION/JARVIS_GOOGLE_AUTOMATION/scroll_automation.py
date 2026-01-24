import pyautogui


def scroll_up(times=15):
    for _ in range(times):
        pyautogui.press('up')

def scroll_down(times=15):
    for _ in range(times):
        pyautogui.press('down')

def scroll_to_top():
    pyautogui.hotkey('home')

def scroll_to_bottom():
    pyautogui.hotkey('end')