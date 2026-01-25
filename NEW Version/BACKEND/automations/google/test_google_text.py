# BACKEND/automations/google/test_google_text.py

from BACKEND.automations.browser.browser_config import (
    get_browser_choice,
    save_browser_choice
)
from BACKEND.automations.google.google_controller import GoogleController
from BACKEND.automations.google.google_session import GoogleBlockedError


def ask_browser_choice():
    print("\nChoose browser:")
    print("1. Chrome")
    print("2. Edge")

    while True:
        c = input("Choice (1/2): ").strip()
        if c == "1":
            save_browser_choice("chrome")
            return
        if c == "2":
            save_browser_choice("edge")
            return
        print("Invalid choice.")


def main():
    print("\n=== Google Automation Test (Text Mode) ===")

    if not get_browser_choice():
        ask_browser_choice()

    google = GoogleController()

    print("\nCommands:")
    print(" search <query>")
    print(" open website <name>")
    print(" scroll down / scroll up")
    print(" scroll top / scroll bottom")
    print(" new tab / close tab")
    print(" next tab / previous tab")
    print(" back / forward / refresh")
    print(" exit")

    while True:
        cmd = input("\n> ").strip().lower()

        try:
            if cmd.startswith("search "):
                google.search(cmd.replace("search ", ""))

            elif cmd.startswith("open website "):
                google.open_site(cmd.replace("open website ", ""))

            elif cmd == "scroll down":
                google.scroll_down()

            elif cmd == "scroll up":
                google.scroll_up()

            elif cmd == "scroll top":
                google.scroll_top()

            elif cmd == "scroll bottom":
                google.scroll_bottom()

            elif cmd == "new tab":
                google.new_tab()

            elif cmd == "close tab":
                google.close_tab()

            elif cmd == "next tab":
                google.next_tab()

            elif cmd == "previous tab":
                google.previous_tab()

            elif cmd == "back":
                google.back()

            elif cmd == "forward":
                google.forward()

            elif cmd == "refresh":
                google.refresh()

            elif cmd == "exit":
                google.close()
                print("👋 Test ended.")
                break

            else:
                print("Unknown command.")

        except GoogleBlockedError as e:
            print("\n🚨 GOOGLE BLOCKED")
            print(e)
            print("Solve CAPTCHA and retry.\n")

        except Exception as e:
            print("❌ Command failed:", e)


if __name__ == "__main__":
    main()
