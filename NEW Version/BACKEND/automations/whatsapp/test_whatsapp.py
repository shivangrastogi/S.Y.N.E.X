# BACKEND/automations/whatsapp/test_whatsapp.py
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController
from BACKEND.automations.whatsapp.whatsapp_config import save_config


def setup():
    browser = input("Browser (edge/chrome): ").strip().lower()
    profile = input("Profile name (Default / Profile 1 etc): ").strip()
    save_config({
        "browser": browser,
        "profile": profile
    })
    print("✅ WhatsApp browser configuration saved")


def send():
    wa = WhatsAppController()
    contact = input("Contact name: ")
    message = input("Message: ")
    wa.send_message(contact, message)


def main():
    print("\n1. Setup WhatsApp browser")
    print("2. Send WhatsApp message")

    choice = input("> ")

    if choice == "1":
        setup()
    elif choice == "2":
        send()


if __name__ == "__main__":
    main()
