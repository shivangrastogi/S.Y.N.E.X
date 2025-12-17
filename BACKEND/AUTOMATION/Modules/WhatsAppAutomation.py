import pywhatkit
from AUTOMATION.Modules.ContactResolver import find_matching_contacts


def send_whatsapp_message(name, message, speaker=None):
    matches = find_matching_contacts(name)

    if not matches:
        return f"I couldn't find any contact named {name}."

    if len(matches) > 1:
        msg = "I found multiple contacts:\n"
        for i, (n, _) in enumerate(matches, 1):
            msg += f"{i}. {n}\n"

        if speaker:
            speaker.speak(msg)
        return msg

    # ✅ Exactly one match
    contact_name, number = matches[0]

    pywhatkit.sendwhatmsg_instantly(
        phone_no=number,
        message=message,
        wait_time=25,  # ⬅ increase
        tab_close=False  # ⬅ DO NOT auto close
    )
    return f"Message sent to {contact_name}."
