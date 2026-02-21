# Path: d:\New folder (2) - JARVIS\backend\run_console.py
import asyncio
from core.speech import SpeakEngine, ListenEngine
from core.language import detect_language, is_meaningful_command


async def main():
    speak_engine = SpeakEngine()
    listen_engine = ListenEngine()
    
    print("System active. Say 'exit' or 'ruk jao' to stop.")
    
    # Start continuous listening mode
    listen_engine.start_listening()
    
    await speak_engine.speak("I am ready. Main taiyaar hoon.", "hi")
    
    try:
        while True:
            # Listen continuously (mic stays open)
            text = listen_engine.listen()
            
            if text:
                # Validate if it's a meaningful command (not just noise/cough/gibberish)
                if not is_meaningful_command(text):
                    # Ignore noise and continue listening silently
                    continue
                    
                # Determine language of input to respond in the same language
                lang = detect_language(text)
                print(f"Detected Language: {lang}")
                
                lower_text = text.lower()
                if "exit" in lower_text or "ruk jao" in lower_text or "band karo" in lower_text or "stop" in lower_text:
                    # Stop listening before speaking
                    listen_engine.stop_listening()
                    await speak_engine.speak("Goodbye! Phir milenge.", lang)
                    break
                
                # Simple interaction logic
                response = ""
                if lang == "hi":
                    if any(phrase in lower_text for phrase in ["kaise ho", "kya haal", "kaisa hai", "kaise hain"]):
                        response = "Main bilkul theek hoon, dhanyavaad. Aap kaise hain?"
                    elif any(phrase in lower_text for phrase in ["naam kya", "kaun ho", "who are you"]):
                        response = "Mera naam Jarvis hai. Main aapka assistant hoon."
                    elif any(phrase in lower_text for phrase in ["kya kar", "kya ho raha"]):
                         response = "Main bas aapki baat sun raha hoon."
                    else:
                        response = f"Maine suna: {text}"
                else:
                    if any(phrase in lower_text for phrase in ["how are you", "how do you do"]):
                        response = "I am doing well, thank you. How are you?"
                    elif "name" in lower_text or "who are you" in lower_text:
                        response = "My name is Jarvis. I am your assistant."
                    else:
                        response = f"I heard: {text}"
                
                # Stop listening while speaking, then restart
                listen_engine.stop_listening()
                await speak_engine.speak(response, lang)
                listen_engine.start_listening()
                
    finally:
        # Cleanup
        listen_engine.stop_listening()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
