import sys
import time
import random
from dotenv import load_dotenv

# ---- CORE IMPORTS ----
from CORE.TTS_Control import JarvisSpeaker, wait_for_speech_complete
from CORE.VoiceInput import listen, hearing
from CORE.Utils.Logger import log_error, log_retrain
from CORE.Utils.Firebase import init_firebase_logger

# ---- BRAIN ----
from BRAIN.NLU.NLU_Core import get_intent

# ---- AUTOMATION ----
from AUTOMATION.ActionRouter import handle_action
from AUTOMATION.Modules.BatteryAutomation import BatteryAutomation

# ---- DATA ----
from DATA.RESOURCES import responses

load_dotenv()

# ---------------- CONFIG ----------------
CONFIDENCE_THRESHOLD = 0.55

WAKE_WORDS = [
    "jarvis",
    "hello jarvis",
    "hey jarvis",
    "wake up",
    "wake me up"
]

# 🚨 OVERRIDE INTENTS (ALWAYS EXECUTE)
ACTION_OVERRIDE_INTENTS = {
    "send_whatsapp_message"
}

# ------------- GLOBAL SINGLETONS -------------
GLOBAL_SPEAKER = None
GLOBAL_BATTERY_AUTOMATION = None


# ---------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------
def heard_wake_word(text: str) -> bool:
    if not text:
        return False
    text = text.lower().strip()
    return any(w in text for w in WAKE_WORDS)


# ---------------------------------------------
# THREAD-SAFE BACKEND LOOP (GUI MODE)
# ---------------------------------------------
def main_loop_threaded(
    speaker_instance,
    update_mic_status_callback,
    append_chat_callback,
    update_nlu_confidence_callback,
    is_running_check
):
    if not speaker_instance or not is_running_check():
        return

    print("🚀 JARVIS backend thread started")

    greeting = random.choice(responses.ONLINE_RESPONSES)
    speaker_instance.speak(greeting)
    append_chat_callback(f"J.A.R.V.I.S.: {greeting}")
    wait_for_speech_complete(timeout=5)

    conversation_active = False

    while is_running_check():
        try:
            command = ""

            # -------- WAIT FOR WAKE WORD --------
            if not conversation_active:
                update_mic_status_callback("AWAITING WAKE WORD", "#9ca3af")
                wait_for_speech_complete(timeout=1.5)

                wake_text = hearing()
                if not heard_wake_word(wake_text):
                    time.sleep(0.4)
                    continue

                update_mic_status_callback("PROCESSING", "#60a5fa")
                speaker_instance.speak("Yes, Sir?", interrupt=True)
                append_chat_callback("J.A.R.V.I.S.: Yes, Sir?")
                wait_for_speech_complete(timeout=4)

                conversation_active = True

            # -------- LISTEN --------
            update_mic_status_callback("LISTENING", "#4ade80")
            wait_for_speech_complete(timeout=2)

            command = listen()
            update_mic_status_callback("PROCESSING", "#60a5fa")

            if not command:
                time.sleep(1)
                continue

            append_chat_callback(f"You (Voice): {command}")

            # -------- NLU --------
            intent, entities, confidence = get_intent(command)
            update_nlu_confidence_callback(confidence)

            if intent is None:
                speaker_instance.speak("Sir, my understanding module appears offline.")
                log_error("NLU_OFFLINE")
                conversation_active = False
                continue

            # -------- ACTION ROUTING (FIXED) --------
            if confidence >= CONFIDENCE_THRESHOLD or intent in ACTION_OVERRIDE_INTENTS:
                action_result = handle_action(
                    speaker=speaker_instance,
                    command=command,
                    intent=intent,
                    entities=entities
                )

                if action_result is False:
                    conversation_active = False
                    break
            else:
                msg = f"NLU_LOW_CONF | '{command}' | {intent} ({confidence:.2f})"
                log_retrain(msg)

                fallback = responses.get_response(intent)
                speaker_instance.speak(fallback)
                append_chat_callback(f"J.A.R.V.I.S.: {fallback}")

            conversation_active = False

        except Exception as e:
            log_error(f"BACKEND_THREAD_ERROR | {e}")
            speaker_instance.speak("Apologies sir, I encountered an internal error.")
            conversation_active = False

    update_mic_status_callback("STANDBY", "#9ca3af")
    print("👋 JARVIS backend thread stopped")


# ---------------------------------------------
# CLI MODE
# ---------------------------------------------
def main_loop_cli():
    global GLOBAL_SPEAKER

    if not GLOBAL_SPEAKER:
        return

    print("🚀 JARVIS CLI mode started")

    GLOBAL_SPEAKER.speak(random.choice(responses.ONLINE_RESPONSES))
    wait_for_speech_complete(timeout=4)

    conversation_active = False

    while True:
        try:
            if not conversation_active:
                wait_for_speech_complete(timeout=1)
                wake_text = hearing()
                if not heard_wake_word(wake_text):
                    continue

                GLOBAL_SPEAKER.speak("Yes, Sir?", interrupt=True)
                wait_for_speech_complete(timeout=3)
                conversation_active = True

            command = listen()
            if not command:
                conversation_active = False
                continue

            intent, entities, confidence = get_intent(command)

            # -------- ACTION ROUTING (FIXED) --------
            if confidence >= CONFIDENCE_THRESHOLD or intent in ACTION_OVERRIDE_INTENTS:
                result = handle_action(
                    speaker=GLOBAL_SPEAKER,
                    command=command,
                    intent=intent,
                    entities=entities
                )
                if result is False:
                    break
            else:
                log_retrain(f"LOW_CONF | {command} | {intent} ({confidence:.2f})")
                GLOBAL_SPEAKER.speak("I'm not fully certain, sir.")

            conversation_active = False

        except KeyboardInterrupt:
            GLOBAL_SPEAKER.speak(random.choice(responses.GOODBYE_RESPONSES))
            sys.exit()

        except Exception as e:
            log_error(f"CLI_FATAL | {e}")
            GLOBAL_SPEAKER.speak("Critical error occurred.")


# ---------------------------------------------
# INITIALIZATION
# ---------------------------------------------
try:
    GLOBAL_SPEAKER = JarvisSpeaker()
    init_firebase_logger()

    GLOBAL_BATTERY_AUTOMATION = BatteryAutomation()
    if not GLOBAL_BATTERY_AUTOMATION.is_alive():
        GLOBAL_BATTERY_AUTOMATION.start()

except Exception as e:
    print(f"❌ FATAL INIT ERROR: {e}")
    log_error(f"INIT_ERROR | {e}")
    GLOBAL_SPEAKER = None


# ---------------------------------------------
# ENTRY POINT
# ---------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting JARVIS backend (CLI Mode)")
    main_loop_cli()
