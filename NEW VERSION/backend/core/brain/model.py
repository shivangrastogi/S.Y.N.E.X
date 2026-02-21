# Path: d:\New folder (2) - JARVIS\backend\core\brain\model.py
import json
import os
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import classification_report

class JarvisBrain:
    def __init__(self, data_path="backend/core/brain/data/intents.json", model_path="backend/core/brain/data/jarvis_model.pkl"):
        # Use absolute paths to avoid issues when running from different directories
        self.data_path = os.path.abspath(data_path)
        self.model_path = os.path.abspath(model_path)
        self.model = None
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        
        if os.path.exists(self.model_path):
            self.load_model()
        else:
            self.train_initial_model()

    def train_initial_model(self):
        """Trains the model using GridSearchCV for optimal performance"""
        print("Training AI brain model with hyperparameter tuning...")
        
        if not os.path.exists(self.data_path):
            print(f"Error: Data file not found at {self.data_path}")
            return

        with open(self.data_path, 'r', encoding='utf-8') as f:
            intents = json.load(f)
        
        X = []
        y = []
        for intent, patterns in intents.items():
            for pattern in patterns:
                X.append(pattern.lower())
                y.append(intent)
        
        if not X:
            print("No training data found.")
            return

        # Split data for a quick evaluation report
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None)

        # Create a pipeline with Tfidf and SVM
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 3), use_idf=True, smooth_idf=True)),
            ('clf', SVC(probability=True, class_weight='balanced'))
        ])

        # Define comprehensive hyperparameters for optimization
        param_grid = {
            'clf__C': [0.1, 1, 10, 100],
            'clf__kernel': ['linear', 'rbf'],
            'clf__gamma': ['scale', 'auto', 0.1, 0.01]
        }

        # Use GridSearchCV to find the best model
        # cv=3 for better cross-validation with larger dataset
        grid_search = GridSearchCV(pipeline, param_grid, cv=min(3, len(set(y))), n_jobs=1, verbose=1)
        grid_search.fit(X_train, y_train)

        print(f"Best parameters found: {grid_search.best_params_}")
        self.model = grid_search.best_estimator_

        # Print evaluation report
        y_pred = self.model.predict(X_test)
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, zero_division=0))

        # Re-train on full dataset with best parameters
        # Merge X and y into a single training set
        print("Finalizing model on full dataset...")
        self.model.fit(X, y)
        self.save_model()
        print("Brain model trained and optimized successfully.")

    def save_model(self):
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.model, f)

    def load_model(self):
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
        except Exception as e:
            print(f"Error loading model: {e}. Retraining...")
            self.train_initial_model()

    def predict(self, text):
        """Predicts the intent and returns (intent, confidence)"""
        if self.model is None:
            return "unknown", 0.0
            
        text = text.lower()
        probs = self.model.predict_proba([text])[0]
        max_idx = np.argmax(probs)
        confidence = probs[max_idx]
        intent = self.model.classes_[max_idx]
        
        return intent, confidence

    def learn(self, text, correct_intent):
        """Continuous learning: Adds new data and retrains"""
        print(f"Learning: '{text}' -> {correct_intent}")
        
        with open(self.data_path, 'r', encoding='utf-8') as f:
            intents = json.load(f)
            
        if correct_intent not in intents:
            intents[correct_intent] = []
            
        if text.lower() not in [p.lower() for p in intents[correct_intent]]:
            intents[correct_intent].append(text)
            
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(intents, f, indent=2)
            
            # Retrain with optimization
            self.train_initial_model()

if __name__ == "__main__":
    # Test training
    brain = JarvisBrain()
    intent, conf = brain.predict("open chrome")
    print(f"Test Predicted: {intent} ({conf:.2f})")
