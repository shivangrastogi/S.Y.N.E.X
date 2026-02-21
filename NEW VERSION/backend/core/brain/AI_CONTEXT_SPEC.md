# JARVIS AI Brain: Technical Specification & Context

This document provides a comprehensive overview of the JARVIS Intent Recognition System. It is designed to be shared with other AI models to provide instant context for development, debugging, or expansion.

---

## 1. System Overview
JARVIS uses a **Hybrid Statistical Intent Engine**. It combines a supervised machine learning model (SVM) with a heuristic feedback loop (Reinforcement Learning) for continuous improvement without requiring a massive dataset.

### Core Stack:
- **Language**: Python 3.10+
- **ML Library**: `scikit-learn`
- **Vectorization**: `TF-IDF` (1-3 grams)
- **Classifier**: `SVC` (Support Vector Classifier) with Probability Estimates

---

## 2. The Core Model (`model.py`)
The purpose of this module is to map a raw string of text to a specific **Intent ID**.

```python
class JarvisBrain:
    def __init__(self, data_path="intents.json", model_path="jarvis_model.pkl"):
        # Initializing the TF-IDF + SVM Pipeline
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 3), use_idf=True)),
            ('clf', SVC(probability=True, class_weight='balanced'))
        ])
        
    def train(self, X, y):
        # Hyperparameter Tuning
        param_grid = {
            'clf__C': [0.1, 1, 10],
            'clf__kernel': ['linear', 'rbf']
        }
        self.grid = GridSearchCV(self.pipeline, param_grid, cv=3)
        self.grid.fit(X, y)
        self.model = self.grid.best_estimator_

    def predict(self, text):
        # Returns (Intent, Confidence Score)
        probs = self.model.predict_proba([text.lower()])[0]
        max_idx = np.argmax(probs)
        return self.model.classes_[max_idx], probs[max_idx]
```

---

## 3. The Learning Loop (`learner.py`)
This handles the **"Unknown"** state. If the confidence score is low (< 0.5), JARVIS enters its learning phase.

1. **Heuristic Guess**: It uses regex/keywords to guess the intent (e.g., "open" -> `open_item`).
2. **Feedback Recording**: It saves the `(Text, GuessedIntent)` pair to `feedback.json`.
3. **Brain Reinforcement**: It triggers `JarvisBrain.learn()`, which appends the new data to the main `intents.json` and initiates an **automatic retraining cycle**.

---

## 4. Data Structures

### `intents.json` (Training Data)
```json
{
  "schedule_event": [
    "schedule a meeting",
    "book an appointment for tomorrow",
    "i want to schedule a meeting about website revamping"
  ],
  "open_item": [
    "open chrome",
    "start notepad",
    "kholo calculate"
  ]
}
```

---

## 5. Implementation Rationale (FAQs for ChatGPT)

**Q: Why SVM instead of BERT/Transformer?**
**A:** SVMs provide sub-millisecond inference on a single CPU core. BERT requires ~100MB+ of RAM and significant latency. For a voice assistant, response speed is more critical than complex semantic depth.

**Q: How does it handle Hindi/English mix (Hinglish)?**
**A:** The `ngram_range=(1, 3)` in the TF-IDF vectorizer captures both individual words and short phrases. This allows it to learn that "kholo" (open) and "chalao" (run) serve the same semantic function as "open" in English.

**Q: How do I add a new intent?**
**A:** Simply add a new key to `intents.json` with 5-10 example phrases and restart the app. JARVIS will automatically detect the missing model and retrain.

---

## 🚦 Integration Prompt for Other AIs
*"I am developing a Python-based voice assistant called JARVIS. It uses an SVM-based intent classifier with a TF-IDF pipeline. It features a continuous learning loop where low-confidence commands are analyzed by a heuristic learner and then used to retrain the model. Please use this context to help me [add new features/debug crashes/refine extraction logic]."*
