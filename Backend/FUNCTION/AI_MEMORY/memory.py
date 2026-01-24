import os

MEMORY_FILE = os.path.join("..", "AI_MEMORY" ,"Data", "memory.txt")

def remember(text: str):
    print("remembering : ")
    os.makedirs("Data", exist_ok=True)
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")

def recall_memory() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def forget_all():
    open(MEMORY_FILE, "w", encoding="utf-8").close()
