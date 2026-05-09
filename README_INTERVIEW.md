# JARVIS v3.0 — Technical Overview & Interview Guide

This document provides a detailed breakdown of the architecture and technologies used in JARVIS v3.0. It is designed to help you explain the project in depth during your interview, even without advanced AI/ML background.

---

## 1. The "Neural Brain" (Intent Classification)

The most advanced part of JARVIS is how it understands **what** you mean. It doesn't just look for keywords; it understands **intent**.

### Tech Stack:
- **Model:** `paraphrase-multilingual-MiniLM-L12-v2` (Sentence-Transformer)
- **Algorithm:** **k-Nearest Neighbors (k-NN)** with Cosine Similarity
- **Logic File:** `core/intent_classifier.py`

### How it works (The Simple Explanation):
Imagine you have a library of "Example Commands" (found in `data/intents.json`). 
- **The Transformer (Encoder):** When you say something, a "Transformer" model converts your sentence into a long list of numbers (called an **Embedding** or a **Vector**). Think of this as a "Mathematical Vibe" of your sentence.
- **k-NN (The Matching):** The k-NN algorithm takes your "Vibe" and compares it against all the examples in the library. It finds the **k** closest matches (we use `k=5`). 
- **Voting:** If 4 out of 5 closest matches are "Open App," Jarvis decides you want to open an app.

### Why k-NN? (Interview Answer):
> "I chose k-NN because it is **transparent and fast**. Unlike deep neural networks that are 'black boxes,' with k-NN I can see exactly which example sentences triggered a specific response. It also allows the system to 'learn' instantly—if I add a new sentence to `intents.json`, the model effectively 'learns' it on the next boot without needing hours of training."

---

## 2. The "Listen" Functionality (Speech-to-Text)

Jarvis needs to convert your voice into text before the "Brain" can process it.

### Tech Stack:
- **Primary:** Google Web Speech API (via `SpeechRecognition` library)
- **Secondary (Fallback):** **Vosk** (Offline Neural Speech Recognition)
- **Logic File:** `core/stt.py`

### How it works:
1. **Microphone Capture:** The system uses the `PyAudio` interface to record audio.
2. **Hinglish Support:** We use the `en-IN` (English-India) locale. This is crucial because it allows Jarvis to understand mixed Hindi-English (e.g., *"Chrome kholo"*).
3. **Hybrid Mode:** If your internet is slow, the system automatically switches to **Vosk**. Vosk is a small, local model that runs on your computer without internet.

---

## 3. The "Speak" Functionality (Text-to-Speech)

Once Jarvis has a response, it needs to say it back to you.

### Tech Stack:
- **Primary:** **Edge-TTS** (Microsoft Azure's Neural Voices)
- **Secondary (Fallback):** **pyttsx3** (System Native TTS)
- **Voice:** `en-IN-NeerjaNeural`
- **Logic File:** `core/tts.py`

### How it works:
1. **Natural Voice:** We use `en-IN-NeerjaNeural` because it sounds like a real Indian person, not a robotic computer. It handles Hinglish pronunciation perfectly.
2. **Audio Processing:** The system generates an MP3 file, caches it in `data/audio_cache`, and plays it using the `pygame` mixer for smooth, non-blocking audio.
3. **Offline Fallback:** If you're offline, it uses `pyttsx3`, which uses the built-in Windows voices.

---

## 4. Key Technical Concepts for your Interview

### A. What are "Embeddings"?
**Answer:** "Embeddings are a way of representing the **meaning** of text as a point in a multi-dimensional space. Sentences with similar meanings (like 'Open Chrome' and 'Chrome start karo') end up very close to each other in this space, even if they use different words."

### B. Why is it "Multilingual"?
**Answer:** "The model I used, `MiniLM-L12-v2`, was trained on millions of sentences across 50+ languages. It understands that 'Kholo' in Hindi means 'Open' in English. This is why Jarvis can handle Hinglish naturally without needing a separate translator."

### C. What is the "Feedback Loop"?
**Answer:** "Jarvis tracks how confident it is. If you say 'Galat hai' (That's wrong), it logs that interaction in a SQLite database. It then uses an **Exponential Moving Average (EMA)** to adjust its 'Confidence Threshold' for that specific command, effectively learning from its mistakes."

---

## 5. Summary of Architecture Flow

1. **User Speaks** → `stt.py` (Converts Audio to Text)
2. **Text Normalization** → `normalizer.py` (Cleans the text)
3. **Neural Brain** → `intent_classifier.py` (Uses **k-NN** to find the Intent)
4. **Entity Extraction** → `entity_extractor.py` (Finds words like "Chrome" or "5 PM")
5. **Skill Execution** → `executor.py` (Opens the app or sets the reminder)
6. **Voice Output** → `tts.py` (Jarvis speaks the confirmation)
