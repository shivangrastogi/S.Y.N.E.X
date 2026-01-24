from AUTOMATION.ActionRouter import handle_action

class DummySpeaker:
    def speak(self, text):
        print("JARVIS:", text)

speaker = DummySpeaker()

command = "send whatsapp message to test saying I will be late"
intent = "send_whatsapp_message"
entities = {}

result = handle_action(
    speaker=speaker,
    command=command,
    intent=intent,
    entities=entities
)

print("RESULT:", result)
