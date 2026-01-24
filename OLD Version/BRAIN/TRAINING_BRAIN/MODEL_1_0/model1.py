import os

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from UTILS.tts_singleton import speak


def load_dataset(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        qna_pairs = [line.strip().split(':', 1) for line in lines if ':' in line]
        dataset = [{'question': q, 'answer': a} for q, a in qna_pairs]

    return dataset


def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    ps = PorterStemmer()
    tokens = word_tokenize(text.lower())
    tokens = [ps.stem(token) for token in tokens if token.isalnum() and token not in stop_words]
    return ' '.join(tokens)



def train_tfidf_vectorizer(dataset):
    corpus = [preprocess_text(qa['question']) for qa in dataset]
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)
    return vectorizer, X


def get_answer(question , vectorizer , X , dataset):
    question = preprocess_text(question)
    question_vec = vectorizer.transform([question])
    similarities = cosine_similarity(question_vec, X)
    best_match_index = similarities.argmax()
    return dataset[best_match_index]['answer']

# def mind(text):
#     dataset_path = r'C:\Users\bosss\Desktop\JARVIS\DATA\BRAIN_DATA\QNA_DATA\qna.txt'
#     dataset = load_dataset(dataset_path)
#     vectorizer , X = train_tfidf_vectorizer(dataset)
#     user_question = text
#     answer = get_answer(user_question , vectorizer , X , dataset)
#     speak(answer)

def mind(text):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(base_dir, '..', '..', '..','DATA', 'BRAIN_DATA', 'QNA_DATA', 'qna.txt')
    dataset_path = os.path.abspath(dataset_path)

    dataset = load_dataset(dataset_path)
    vectorizer, X = train_tfidf_vectorizer(dataset)
    user_question = text
    answer = get_answer(user_question, vectorizer, X, dataset)
    speak(answer)

mind("what is my name")