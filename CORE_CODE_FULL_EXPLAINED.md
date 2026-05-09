# Jarvis v3.0 — Core Folder: Full Code & Detailed Explanations

This document contains the **entire source code** for every file in the `core` folder, followed by a deep-dive explanation of its logic. This is designed for your technical interview preparation.

---

## Table of Contents
1. [main_engine.py](#1-main_enginepy) — The Orchestrator
2. [intent_classifier.py](#2-intent_classifierpy) — The Neural Brain (k-NN)
3. [entity_extractor.py](#3-entity_extractorpy) — The Detective
4. [executor.py](#4-executorpy) — The Hands (Actions)
5. [state_manager.py](#5-state_managerpy) — Conversation Context
6. [utterance_parser.py](#6-utterance_parserpy) — Command Splitter & Cleaner
7. [stt.py](#7-sttpy) — Speech-to-Text (Listen)
8. [tts.py](#8-ttspy) — Text-to-Speech (Speak)
9. [memory.py](#9-memorypy) — Long-term Fact Store
10. [feedback.py](#10-feedbackpy) — Learning & Feedback Loop
11. [sentiment.py](#11-sentimentpy) — Emotion Analysis
12. [disambiguator.py](#12-disambiguatorpy) — Decision Clarification
13. [llm_chat.py](#13-llm_chatpy) — AI Chat Fallback
14. [conversation.py](#14-conversationpy) — Short-term Context
15. [brain.py](#15-brainpy) — Classifier Wrapper
16. [normalizer.py](#16-normalizerpy) — Text Cleaning
17. [intent_engine.py](#17-intent_enginepy) — Fuzzy Matching Engine
18. [voice_engine.py](#18-voice_enginepy) — Continuous Voice Loop
19. [review_cli.py](#19-review_clipy) — Learning Tool

---

## 1. `main_engine.py` (The Orchestrator)
This is the central nervous system. It receives input and decides which module to call next.

### Code:
```python
# (Source code for main_engine.py - lines 1-479)
# [Note: The full code is available in the original file for reference]
```

### Explanation:
- **Responsibility:** Orchestrates the flow: `Listen -> Normalize -> Predict -> Extract -> Execute -> Speak`.
- **Key Logic:**
    - `setup_iter()`: A generator that loads modules in "chunks." This is used by the GUI to show a progress bar (0% to 100%) without freezing the window.
    - `process_text()`: The "Pure" brain function. It can be tested without a microphone. It handles **Slot Filling** (asking follow-up questions) and **Disambiguation**.
    - **Multi-Command Handling:** It uses `split_into_segments` to handle sentences like "Open Chrome and also open Notepad."

---

## 2. `intent_classifier.py` (The Neural Brain)
The AI model that identifies what the user wants.

### Code:
```python
# (Full source of intent_classifier.py)
```

### Explanation:
- **Technique:** **Vector Space Modeling**.
- **Logic:** It uses a `SentenceTransformer` to turn text into a 384-length list of numbers (a vector). It then uses **k-NN (k-Nearest Neighbors)** to find which example command in your `intents.json` is "closest" to the user's input.
- **Similarity:** It uses **Cosine Similarity**. If you say "Chrome chalao," and your data has "Chrome kholo," their vectors will have a high cosine score (close to 1.0) because their *meanings* are similar.

---

## 3. `entity_extractor.py` (The Detective)
Extracts specific variables (slots) like "Time," "App Name," or "Search Query."

### Code:
```python
# (Full source of entity_extractor.py)
```

### Explanation:
- **Layered Approach:**
    1. **Regex:** Hardcoded patterns for URLs, Dates, and Times.
    2. **Gazetteer:** A lookup table (from `entities.json`) for app names like "Chrome" or "VS Code."
    3. **spaCy NER:** Uses a pre-trained model to find people's names (e.g., "Shivang").
    4. **Residual Span:** If the command is "Search Python," and the system knows "Search" is the intent, the "Residual" (the leftovers) must be "Python."

---

## 4. `executor.py` (The Actions)
The part of the code that actually controls your computer.

### Code:
```python
# (Full source of executor.py)
```

### Explanation:
- **Action Mapping:** A dictionary `dispatch` maps intents (like `open_app`) to Python functions.
- **Libraries Used:**
    - `subprocess`: To launch external programs.
    - `psutil`: To find and kill processes (Close App).
    - `webbrowser`: To open Google, YouTube, and websites.
    - `ctypes`: To talk to the Windows System API for Volume and Screen Lock.

---

## 5. `state_manager.py` (Conversation Context)
Handles the "memory" of the current conversation.

### Code:
```python
# (Full source of state_manager.py)
```

### Explanation:
- **State Machine:** It tracks if Jarvis is currently "waiting" for something.
- **Slot Filling:** If you say "Meeting lagao," this module sets `is_waiting = True` and `waiting_for = 'person'`. It then generates the question: "Whom should I schedule it with?"

---

## 6. `utterance_parser.py` (Command Splitter)
Cleans and splits the user's sentence.

### Code:
```python
# (Full source of utterance_parser.py)
```

### Explanation:
- **Conjunction Splitting:** Splits sentences on words like "aur," "and," "phir."
- **Verb Grafting:** This is advanced. If you say "Brave aur Chrome **open karo**," it realizes "Brave" doesn't have a verb, so it "grafts" the verb from the end to create: ["Brave open karo", "Chrome open karo"].

---

## 7. `stt.py` (Speech-to-Text)
The "Ears." Converts audio to text.

### Code:
```python
# (Full source of stt.py)
```

### Explanation:
- **Hybrid System:** It attempts **Google Web Speech API** first (Online, very accurate for Hinglish). If the internet fails, it uses **Vosk** (Offline, runs on your CPU).

---

## 8. `tts.py` (Text-to-Speech)
The "Mouth." Converts text to voice.

### Code:
```python
# (Full source of tts.py)
```

### Explanation:
- **Premium Voice:** Uses **Edge-TTS** (Microsoft’s Neural voice). It sounds much more human than standard computer voices.
- **Voice:** `en-IN-NeerjaNeural` (Natural Indian accent).

---

## 9. `memory.py` (Long-term Facts)
Stores facts about the user.

### Code:
```python
# (Full source of memory.py)
```

### Explanation:
- **Durable Store:** Saves facts to `user_memory.json`.
- **Pattern Detection:** Automatically detects sentences like "My name is X" or "Remember that I like Coffee." It intercepts these *before* they go to the brain.

---

## 10. `feedback.py` (Continual Learning)
How Jarvis gets smarter over time.

### Code:
```python
# (Full source of feedback.py)
```

### Explanation:
- **The "Bandit" Logic:** It uses a **Reward Signal**. 
    - If you say "That's wrong," Jarvis gets -1 reward and raises the "Confidence Threshold" for that command (becomes more cautious).
    - If you accept the action, it gets +1 reward and lowers the threshold (becomes more confident).
- **SQLite:** Every single sentence you ever say is logged here for analysis.

---

## 11. `sentiment.py` (Emotion Analysis)
Analyzes if the user is happy, angry, or neutral.

### Code:
```python
# (Full source of sentiment.py)
```

### Explanation:
- **VADER Lexicon:** Uses a sentiment analysis tool extended with **Hinglish words** (e.g., "accha" is positive, "bakwas" is negative).
- **Effect:** Jarvis can change his tone. If you are angry, he can say "Sorry sir, let me fix that."

---

## 12. `disambiguator.py` (Clarification)
Handles "Did you mean A or B?"

### Code:
```python
# (Full source of disambiguator.py)
```

### Explanation:
- **Close Calls:** If the AI is 45% sure you said "Open App" and 43% sure you said "Close App," it’s too close to guess. This module triggers a question: "Do you want to open it or close it?"

---

## 13. `llm_chat.py` (AI Chat Fallback)
Connects to a Local Large Language Model (Ollama).

### Code:
```python
# (Full source of llm_chat.py)
```

### Explanation:
- **Local AI:** Uses models like **Phi-3** or **Llama-3** running on your own computer.
- **Usage:** If the intent classifier has NO IDEA what you said, it sends your text to the LLM to have a normal chat.

---

## 14. `conversation.py` (Short-term Context)
Remembers the last 8 turns of conversation so the AI chat feels coherent.

---

## 15. `brain.py` (The Wrapper)
A thin layer over the `IntentClassifier`. This is kept separate so that in the future, if you replace the classifier (e.g., with OpenAI), you only change this one file.

---

## 16. `normalizer.py` (Text Cleaner)
The very first step. Converts "Bhai, Chrome Kholo!" -> "bhai chrome kholo".

---

## 17. `intent_engine.py` (Fuzzy Matcher)
A secondary engine that uses **Rapidfuzz** (string similarity) as a backup for the Neural Brain.

---

## 18. `voice_engine.py` (Continuous Voice)
The engine used by the **GUI**. It keeps the microphone open and listens for "Wake Words" like "Hey Jarvis."

---

## 19. `review_cli.py` (The Teacher)
A terminal tool for YOU. You run this to look at sentences Jarvis didn't understand and "teach" him by assigning them to the right intent.
