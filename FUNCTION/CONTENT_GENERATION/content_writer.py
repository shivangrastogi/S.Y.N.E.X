import os
import subprocess
from groq import Groq
from UTILS.tts_singleton import speak


def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set; cannot generate content.")
    return Groq(api_key=api_key)


messages = []

system_prompt = {
    "role": "system",
    "content": "You are a helpful assistant that writes formal content based on user topics. Write in good English, suitable for official use."
}


def ContentWriterAI(topic: str) -> str:
    client = _get_client()

    messages.clear()
    messages.append(system_prompt)
    messages.append({
        "role": "user",
        "content": topic
    })

    response = client.chat.completions.create(
        model="mistral-saba-24b",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        top_p=1
    )

    result = response.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": result})
    return result


def generate_content_file(topic: str):
    filename = os.path.join("Data", f"{topic.lower().replace(' ', '_')}.txt")
    os.makedirs("Data", exist_ok=True)

    try:
        speak(f"Generating content for {topic}")
        content = ContentWriterAI(topic)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.Popen(["notepad.exe", filename])
    except Exception as e:
        speak("Sorry, something went wrong during content creation.")
        print(f"[Content Error] {e}")
