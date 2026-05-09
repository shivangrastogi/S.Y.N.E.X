# AI Engineer Interview Preparation Guide (Jarvis v3.0 focus)

This guide maps your **Jarvis v3.0** project directly to the Job Description (JD) for the AI Engineer role at Vaco Binary Semantics. 

---

## 1. JD Skills Mapping (The Evidence)

The interviewer will ask if you have experience with specific technologies. Use these "Proof Points" from your code.

| JD Requirement | How you meet it in Jarvis v3.0 | File Reference |
| :--- | :--- | :--- |
| **Python Proficiency** | Entire system built in Python 3.10+ using classes and async. | `main.py`, `core/` |
| **Machine Learning** | Implemented **k-Nearest Neighbors (k-NN)** for classification. | `intent_classifier.py` |
| **NLP** | Used **spaCy** for Named Entity Recognition and custom regex for slot filling. | `entity_extractor.py` |
| **LLMs (GPT, LLaMA)** | Integrated **Ollama** to run local models (Phi-3/Llama-3) for chat fallback. | `llm_chat.py` |
| **Embeddings** | Used `sentence-transformers` (**MiniLM**) to create 384D text vectors. | `intent_classifier.py` |
| **Vector Databases** | Built a vector search engine using **Cosine Similarity** and k-NN. | `intent_classifier.py` |
| **Data Preprocessing** | Created a custom **Normalizer** and **Utterance Parser** for Hinglish. | `normalizer.py` |
| **SQL / Databases** | Logged every interaction and reward into an **SQLite** database. | `feedback.py` |

---

## 2. Technical Q&A (High-Level AI Concepts)

### Q1: Explain your Intent Classification architecture.
**Answer:** "I used a **Retrieval-based NLU** approach. Instead of training a rigid classifier, I use a **frozen encoder** (`MiniLM-L12-v2`) to turn input text into a vector. I then perform a **similarity search** against a library of known intent patterns. 
**Why?** This makes the system 'few-shot'. I can add a new command to `intents.json` and it works immediately without retraining the whole model."

### Q2: How do you handle the "Hinglish" (Hindi + English) problem?
**Answer:** "I use a **Multilingual Embedding model**. These models are trained on parallel corpora of 50+ languages. In the vector space, the word 'Open' and the Hindi word 'Kholo' end up very close to each other. I also built a custom `utterance_parser` that handles common Hinglish grammar, like verb-grafting in sentences like 'Chrome aur Notepad *open karo*'."

### Q3: What is "Slot Filling" and how did you implement it?
**Answer:** "Slot filling is extracting the variables needed for a command. For example, 'Set a reminder' needs a *time* and a *message*. I used a `StateManager` to track the conversation. If a slot is missing, Jarvis enters a 'waiting' state and asks the user: 'At what time?'. Once the user answers, the `entity_extractor` pulls the new data and completes the execution."

### Q4: How do you evaluate and improve your AI model?
**Answer:** "I implemented a **Feedback Loop** based on a Contextual Bandit approach. Every time Jarvis acts, the user can say 'Galat hai' (That's wrong). My `feedback.py` records this as a -1 reward in **SQLite** and automatically raises the **Confidence Threshold** for that specific intent, making the AI more 'careful' in the future."

---

## 3. Advanced Topics (LLMs & RAG)

### Q5: What are Embeddings and why do they matter?
**Answer:** "Embeddings are dense vector representations of text that capture semantic meaning. In my project, they allow Jarvis to understand that 'Play a song' and 'Music chalao' are the same thing, even though they share zero keywords."

### Q6: Have you worked with Vector Databases like FAISS or Pinecone?
**Answer:** "In this project, I used a k-NN approach with **Cosine Similarity** for the vector search. For larger production scales, I would move the `intent_index` into **FAISS** (Facebook AI Similarity Search) to handle millions of vectors with sub-millisecond latency."

---

## 4. Behavioral / Workflow Questions

### Q7: What does a typical day look like for you as an AI Engineer?
**Answer:** "I start by reviewing the **Feedback Logs** (SQLite) to see where the model failed. I then perform **Data Augmentation** by adding failed sentences to the training set. Most of my time is spent on **Prompt Engineering** for the LLM fallback or refining the **Entity Extraction** rules to handle edge cases in user speech."

### Q8: How do you document your AI experiments?
**Answer:** "I maintain a systematic `README` and code comments. For Jarvis, I use a `feedback_log.sqlite` which acts as a living document of every 'experiment' (utterance) the AI has faced, tracking the Input, the Predicted Intent, and the User's final Feedback."
