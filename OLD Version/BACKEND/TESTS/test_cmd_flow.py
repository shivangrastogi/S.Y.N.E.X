import random
from AUTOMATION.ActionRouter import handle_action
from CORE.TTS_Control import JarvisSpeaker
from reset_user_state import reset_user_state
from BACKEND.TESTS.command_router import detect_intent_from_command

def main():
    reset_user_state()

    speaker = JarvisSpeaker()

    print("🧪 JARVIS CMD TEST MODE (COMMAND BASED)")
    print("Examples:")
    print("  - create my profile")
    print("  - refresh my contacts")
    print("  - send whatsapp to aman saying i will be late")
    print("Type 'exit' to quit\n")

    while True:
        command = input(">>> ").strip()
        if command == "exit":
            break

        intent = detect_intent_from_command(command)

        if not intent:
            print("❌ Could not understand command")
            continue

        print(f"\n🧠 Detected intent: {intent}")
        print(f"🗣 Command: {command}")

        handle_action(
            speaker=speaker,
            command=command,
            intent=intent,
            entities={}
        )

        print("-" * 50)

if __name__ == "__main__":
    main()
