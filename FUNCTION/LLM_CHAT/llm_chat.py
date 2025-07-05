# # llm_chat.py
# import os
# import sys
# from llama_cpp import Llama
# from FUNCTION.JARVIS_SPEAK.speak import speak
#
# def get_model_path():
#     if getattr(sys, 'frozen', False):
#         base_dir = sys._MEIPASS
#     else:
#         base_dir = os.path.dirname(os.path.abspath(__file__))
#     return os.path.join(base_dir, "MODELS", "zephyr-7b-beta.Q2_K.gguf")
#
# def add_llama_dll_directory():
#     if getattr(sys, 'frozen', False):
#         dll_path = os.path.join(sys._MEIPASS, "llama_cpp")
#         if os.path.exists(dll_path):
#             os.add_dll_directory(dll_path)
#
# def normal_chat(prompt: str):
#     try:
#         add_llama_dll_directory()
#         model_path = get_model_path()
#
#         if not os.path.exists(model_path):
#             speak("Model file is missing.")
#             return
#
#         llm = Llama(
#             model_path=model_path,
#             n_ctx=2048,
#             n_threads=4,
#             n_batch=16,
#             verbose=False
#         )
#
#         response = llm(
#             prompt=f"User: {prompt}\nAssistant:",
#             stop=["User:", "Assistant:"],
#             temperature=0.7,
#             max_tokens=100,
#             echo=False
#         )
#
#         answer = response["choices"][0]["text"].strip()
#         speak(answer if answer else "Sorry, I couldn't generate a response.")
#     except Exception as e:
#         print(f"[LLM ERROR] {e}")
#         speak("There was an error loading the model.")
