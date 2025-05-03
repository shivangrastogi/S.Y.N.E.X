from AUTOMATION.COMMON_AUTOMATION.close import *
from AUTOMATION.COMMON_AUTOMATION.open import *

def common_cmd(text):
    if "close" in text or "band kar do" in text:
        close()
    else:
        pass