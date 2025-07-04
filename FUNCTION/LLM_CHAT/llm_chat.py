# llm_chat.py
import os
from llama_cpp import Llama
from FUNCTION.JARVIS_SPEAK.speak import speak

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "MODELS", "zephyr-7b-beta.Q2_K.gguf"))

def normal_chat(prompt: str):
    try:
        # ✅ Lazy-load the model only when this function is called
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=4,
            n_batch=16,
            verbose=False
        )

        response = llm(
            prompt=f"User: {prompt}\nAssistant:",
            stop=["User:", "Assistant:"],
            temperature=0.7,
            max_tokens=100,
            echo=False
        )

        answer = response["choices"][0]["text"].strip()
        if answer:
            speak(answer)
        else:
            speak("Sorry, I couldn't generate a response.")

    except Exception as e:
        print(f"[normal_chat ERROR]: {e}")
        speak("There was an error processing your request.")


# import os
# from llama_cpp import Llama
# from FUNCTION.JARVIS_SPEAK.speak import speak
#
# # Relative model path
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# MODEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "MODELS", "zephyr-7b-beta.Q2_K.gguf"))
#
# # Load the LLM
# llm = Llama(
#     model_path=MODEL_PATH,
#     n_ctx=2048,
#     n_threads=4,
#     n_batch=16,
#     verbose=False
# )
#
# def normal_chat(prompt: str):
#     response = llm(
#         prompt=f"User: {prompt}\nAssistant:",
#         stop=["User:", "Assistant:"],
#         temperature=0.7,
#         max_tokens=100,
#         echo=False
#     )
#     answer = response["choices"][0]["text"].strip()
#     if answer:
#         speak(answer)
#     else:
#         speak("Sorry, I couldn't generate a response.")
#
