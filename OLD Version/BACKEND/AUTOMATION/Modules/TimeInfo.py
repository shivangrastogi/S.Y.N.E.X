from datetime import datetime

def get_time_report():
    """
    Returns a human-friendly time string.
    """
    now = datetime.now()

    time_str = now.strftime("%I:%M %p")  # 12-hour format
    date_str = now.strftime("%A, %d %B %Y")

    return f"Sir, the current time is {time_str} on {date_str}."
