import nltk
from nltk.stem import WordNetLemmatizer
import pickle
import numpy as np
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tensorflow.keras.models import load_model
from core.normalizer import HinglishNormalizer


class NeuralEngine:
    def __init__(self, model_path='data/models/jarvis_model.h5', 
                 words_path='data/models/words.pkl', 
                 classes_path='data/models/classes.pkl'):
        
        self.lemmatizer = WordNetLemmatizer()
        self.normalizer = HinglishNormalizer()
        
        # Load the model and data
        if os.path.exists(model_path):
            self.model = load_model(model_path)
            self.words = pickle.load(open(words_path, 'rb'))
            self.classes = pickle.load(open(classes_path, 'rb'))
            print("Neural Brain loaded successfully.")
        else:
            print("Error: Neural Model not found. Please run core/trainer.py first.")

    def clean_up_sentence(self, sentence):
        # Normalize Hinglish first
        sentence = self.normalizer.normalize(sentence)
        
        # Tokenize and Lemmatize
        sentence_words = nltk.word_tokenize(sentence)
        sentence_words = [self.lemmatizer.lemmatize(word.lower()) for word in sentence_words]
        return sentence_words

    def bow(self, sentence, show_details=False):
        # Bag of Words array
        sentence_words = self.clean_up_sentence(sentence)
        bag = [0] * len(self.words)
        for s in sentence_words:
            for i, w in enumerate(self.words):
                if w == s:
                    bag[i] = 1
                    if show_details:
                        print(f"found in bag: {w}")
        return np.array(bag)

    def predict_intent(self, sentence, threshold=0.75):
        # Get bag of words
        p = self.bow(sentence)
        
        # Get predictions
        res = self.model.predict(np.array([p]))[0]
        
        # Filter out predictions below a threshold
        results = [[i, r] for i, r in enumerate(res) if r > threshold]
        
        # Sort by strength of probability
        results.sort(key=lambda x: x[1], reverse=True)
        
        return_list = []
        for r in results:
            return_list.append({"intent": self.classes[r[0]], "probability": str(r[1])})
            
        return return_list

if __name__ == "__main__":
    engine = NeuralEngine()
    
    # Test cases for unseen variations
    test_queries = [
        "bhai chrome open kardo",
        "band karo notepad",
        "mausam ka kya haal hai",
        "play a song please"
    ]
    
    for query in test_queries:
        prediction = engine.predict_intent(query)
        print(f"Query: '{query}' -> Prediction: {prediction}")
