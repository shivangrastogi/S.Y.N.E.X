# # chat_mode.py (offline distilgpt2)
# import os
# os.environ["TRANSFORMERS_NO_TF"] = "1"
# from transformers import AutoTokenizer, AutoModelForCausalLM
# import torch
# from FUNCTION.JARVIS_SPEAK.speak import speak
# import os
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "MODELS", "microsoft","DialoGPT-small-offline"))
#
# # Load model and tokenizer from disk (offline)
# tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
# model = AutoModelForCausalLM.from_pretrained(MODEL_DIR)
#
# def distil_chat(prompt: str):
#
#     try:
#         input_ids = tokenizer.encode(prompt, return_tensors='pt')
#         output = model.generate(input_ids, max_length=100, pad_token_id=tokenizer.eos_token_id)
#         response = tokenizer.decode(output[:, input_ids.shape[-1]:][0], skip_special_tokens=True)
#         speak(response)
#         return response
#     except Exception as e:
#         print(f"[distil_chat ERROR]: {e}")
#         speak("There was an error generating the response.")
#         return ""
#
