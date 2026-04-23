import json
import pickle
import numpy as np
import os
import nltk
from nltk.stem import WordNetLemmatizer
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import SGD

# Download necessary NLTK data
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('punkt_tab')


class JarvisTrainer:
    def __init__(self, intents_path='data/intents.json'):
        self.intents_path = intents_path
        self.lemmatizer = WordNetLemmatizer()
        self.words = []
        self.classes = []
        self.documents = []
        self.ignore_words = ['?', '!', '.', ',']

    def prepare_data(self):
        # Load intents
        with open(self.intents_path, 'r') as f:
            intents = json.load(f)

        for intent_name, patterns in intents.items():
            # Add intent name to classes
            if intent_name not in self.classes:
                self.classes.append(intent_name)
            
            for pattern in patterns:
                # Tokenize each word
                w = nltk.word_tokenize(pattern)
                self.words.extend(w)
                # Add documents in the corpus
                self.documents.append((w, intent_name))

        # Lemmatize and lower each word and remove duplicates
        self.words = [self.lemmatizer.lemmatize(w.lower()) for w in self.words if w not in self.ignore_words]
        self.words = sorted(list(set(self.words)))
        self.classes = sorted(list(set(self.classes)))

        print(f"{len(self.documents)} documents")
        print(f"{len(self.classes)} classes: {self.classes}")
        print(f"{len(self.words)} unique lemmatized words: {self.words}")

        # Save words and classes for the predictor to use later
        os.makedirs('data/models', exist_ok=True)
        pickle.dump(self.words, open('data/models/words.pkl', 'wb'))
        pickle.dump(self.classes, open('data/models/classes.pkl', 'wb'))

    def create_training_data(self):
        training = []
        output_empty = [0] * len(self.classes)

        for doc in self.documents:
            bag = []
            pattern_words = doc[0]
            pattern_words = [self.lemmatizer.lemmatize(word.lower()) for word in pattern_words]
            
            # Create bag of words array
            for w in self.words:
                bag.append(1) if w in pattern_words else bag.append(0)

            # Output is a '0' for each tag and '1' for current tag
            output_row = list(output_empty)
            output_row[self.classes.index(doc[1])] = 1
            training.append([bag, output_row])

        # Shuffle and convert to numpy array
        np.random.shuffle(training)
        training = np.array(training, dtype=object)

        train_x = list(training[:,0])
        train_y = list(training[:,1])
        return np.array(train_x), np.array(train_y)

    def train(self, train_x, train_y):
        # Build the model - 3 layers
        model = Sequential()
        model.add(Dense(128, input_shape=(len(train_x[0]),), activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(len(train_y[0]), activation='softmax'))

        # Compile model
        sgd = SGD(learning_rate=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        model.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])

        # Fit and save the model
        print("Training the Neural Brain...")
        hist = model.fit(np.array(train_x), np.array(train_y), epochs=200, batch_size=5, verbose=1)
        model.save('data/models/jarvis_model.h5', hist)
        print("Model created and saved successfully.")

if __name__ == "__main__":
    trainer = JarvisTrainer()
    trainer.prepare_data()
    x, y = trainer.create_training_data()
    trainer.train(x, y)
