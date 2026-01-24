import re

def extract_name_and_message(command: str):
    """
    Examples:
    send whatsapp message to test saying I will be late
    whatsapp message to mom that I reached home
    """

    pattern = r"(?:to)\s+([\w\s]+?)\s+(?:saying|that)\s+(.+)"
    match = re.search(pattern, command, re.IGNORECASE)

    if not match:
        return None, None

    name = match.group(1).strip()
    message = match.group(2).strip()

    return name, message
