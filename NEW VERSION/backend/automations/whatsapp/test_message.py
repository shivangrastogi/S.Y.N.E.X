# BACKEND/automations/whatsapp/test_message.py
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController


def main():
    print("\n🧪 WhatsApp Web Test")
    print("Sending default message...")

    wa = WhatsAppController()

    wa.send_message(
        contact="Neha Rajput",
        message="hello"
    )

    print("✅ Message flow executed")


if __name__ == "__main__":
    main()
