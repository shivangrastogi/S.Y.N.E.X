"""Image generation via Hugging Face API.

Requires environment variable HUGGINGFACE_API_KEY.
"""
import asyncio
from random import randint
from PIL import Image, UnidentifiedImageError
import requests
import os
from time import sleep
from FUNCTION.JARVIS_SPEAK.speak import speak


def _get_api_key() -> str:
    key = os.getenv("HUGGINGFACE_API_KEY")
    if not key:
        raise RuntimeError("HUGGINGFACE_API_KEY is not set; cannot generate images.")
    return key


def _headers():
    return {"Authorization": f"Bearer {_get_api_key()}"}


API_URL = "https://api-inference.huggingface.co/models/prompthero/openjourney"

# Directory setup
DATA_DIR = "Data"
FRONTEND_DATA_PATH = os.path.join("..", "..", "Frontend", "Files", "ImageGeneration.data")
os.makedirs(DATA_DIR, exist_ok=True)


def sanitize_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in text.replace(" ", "_"))


async def query(payload):
    headers = _headers()
    try:
        response = await asyncio.to_thread(requests.post, API_URL, headers=headers, json=payload)
        content_type = response.headers.get("Content-Type", "")
        if "image" in content_type:
            return response.content
        else:
            print("Not an image. Response:", response.text)
            return None
    except Exception as e:
        print("API Error:", e)
        return None


async def generate_images(prompt: str):
    payload = {"inputs": prompt}
    image_bytes = await query(payload)
    if not image_bytes:
        speak("Sorry, I could not generate the image.")
        return

    filenames = [f"{sanitize_filename(prompt)}{i}.jpg" for i in range(1, 5)]
    for filename in filenames:
        path = os.path.join(DATA_DIR, filename)
        with open(path, "wb") as f:
            f.write(image_bytes)
        print(f"Saved: {path}")
    open_images(prompt)


def open_images(prompt):
    filenames = [f"{sanitize_filename(prompt)}{i}.jpg" for i in range(1, 5)]
    for filename in filenames:
        path = os.path.join(DATA_DIR, filename)
        try:
            img = Image.open(path)
            img.verify()
            img = Image.open(path)
            img.show()
            print(f"Opened: {path}")
            sleep(1)
        except (IOError, UnidentifiedImageError):
            print(f"Could not open or invalid image: {path}")


def GenerateImages(prompt):
    asyncio.run(generate_images(prompt))
    speak("Image generation completed, sir.")


def ImageGeneratorLoop():
    while True:
        try:
            if not os.path.exists(FRONTEND_DATA_PATH):
                sleep(1)
                continue

            with open(FRONTEND_DATA_PATH, "r") as f:
                data = f.read().strip()

            if not data or "," not in data:
                sleep(1)
                continue

            prompt, status = data.split(",", 1)
            prompt = prompt.strip()
            status = status.strip().lower()

            if status == "true" and prompt:
                speak(f"Generating images for {prompt}")
                GenerateImages(prompt)

                with open(FRONTEND_DATA_PATH, "w") as f:
                    f.write("False,False")

            sleep(2)

        except Exception as e:
            print("Error in image generation loop:", e)
            sleep(2)


if __name__ == "__main__":
    ImageGeneratorLoop()
