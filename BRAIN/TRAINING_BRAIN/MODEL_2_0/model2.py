import json
import random
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# Load the data
with open(r'C:\Users\bosss\Desktop\JARVIS\DATA\BRAIN_DATA\QNA_DATA\qna.json') as file:
    data = json.load(file)

training_data = []

# Extract patterns and tags
for intent in data.get('intents', []):
    if 'patterns' in intent:
        for pattern in intent['patterns']:
            training_data.append((pattern, intent['tag']))
    else:
        print(f"Warning: 'patterns' key is missing in intent: {intent}")

# Check if data is loaded
if not training_data:
    print("Error: No training data found.")
else:
    # Split patterns (x) and tags (y)
    x, y = zip(*training_data)

    # Vectorize patterns
    vectorizer = CountVectorizer()
    x = vectorizer.fit_transform(x)

    # Train classifier
    classifier = MultinomialNB()
    classifier.fit(x, y)

    # Function to predict response
    def get_response(user_input):
        user_input_vectorized = vectorizer.transform([user_input])
        predicted_intent = classifier.predict(user_input_vectorized)[0]

        for intent in data.get('intents', []):
            if intent.get('tag') == predicted_intent:
                responses = intent.get('responses', [])
                if responses:
                    return random.choice(responses)
                else:
                    return "I'm sorry, I don't have a response for that."


# Example usage
x = get_response("hi I am shivang")
print(x)