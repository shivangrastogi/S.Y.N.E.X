# Path: d:\New folder (2) - JARVIS\backend\core\language\detector.py
"""
Language Detector Module
Detects whether text is Hindi (Hinglish) or English based on keyword analysis.
"""


def detect_language(text):
    """
    Detects if the text is Hindi (Hinglish) or English based on common keywords.
    Since input is now 'en-IN', everything is in Latin script.
    """
    if not text:
        return "en"
    
    text = text.lower()
    # Common Hindi words often used in Hinglish
    hindi_keywords = [
        "kya", "kaise", "karo", "haan", "nahin", "namaste", "tum", "aap", 
        "hal", "kahan", "kab", "kyon", "theek", "accha", "bura", "karta", 
        "karti", "bol", "sun", "samajh", "hindi", "bhai", "dost", "yaar"
    ]
    
    # Check for presence of Hindi keywords
    words = text.split()
    for word in words:
        if word in hindi_keywords:
            return "hi"
            
    # Default to English if no clear Hindi keywords found
    return "en"
