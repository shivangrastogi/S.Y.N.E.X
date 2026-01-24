import asyncio
from random import randint
from PIL import Image, UnidentifiedImageError
import requests
import os
from time import sleep
from UTILS.tts_singleton import speak


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


# Clean filename generator
def sanitize_filename(text):
    return "".join(c if c.isalnum() or c == "_" else "_" for c in text.replace(" ", "_"))


# Open and show images
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


# Hugging Face image generation
async def query(payload):
    try:
        response = await asyncio.to_thread(requests.post, API_URL, headers=_headers(), json=payload)
        content_type = response.headers.get("Content-Type", "")
        if "image" in content_type:
            return response.content
        else:
            print("Not an image. Response:", response.text)
            return None
    except Exception as e:
        print("API Error:", e)
        return None


# Generate 4 images
async def generate_images(prompt):
    tasks = []
    for _ in range(4):
        payload = {
            "inputs": f"{prompt}, quality=4K, sharpness=maximum, Ultra High details, high resolution, seed={randint(0, 999999)}"
        }
        tasks.append(asyncio.create_task(query(payload)))

    results = await asyncio.gather(*tasks)
    for i, img_bytes in enumerate(results):
        if not img_bytes or len(img_bytes) < 10000:
            print(f"Skipping invalid image {i+1}")
            continue

        path = os.path.join(DATA_DIR, f"{sanitize_filename(prompt)}{i+1}.jpg")
        with open(path, "wb") as f:
            f.write(img_bytes)
        print(f"Saved: {path}")


# Complete generation wrapper
def GenerateImages(prompt):
    asyncio.run(generate_images(prompt))
    open_images(prompt)
    speak("Image generation completed, sir.")


# Loop that listens for frontend signal
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
