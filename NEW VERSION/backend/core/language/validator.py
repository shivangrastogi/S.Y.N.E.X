# Path: d:\New folder (2) - JARVIS\backend\core\language\validator.py
"""
Validator Module
Validates if recognized text is a meaningful command or just noise.
"""


def is_meaningful_command(text):
    """
    Checks if the recognized text is a meaningful command or just noise/gibberish.
    Returns True if it's a valid command, False if it should be ignored.
    """
    if not text or len(text.strip()) < 2:
        return False
    
    text_lower = text.lower().strip()
    
    # Minimum word count - single random words are usually noise
    words = text_lower.split()
    if len(words) < 2:
        # Allow single-word commands only if they're in the whitelist
        single_word_commands = {'exit', 'stop', 'hello', 'hi', 'namaste', 'bye'}
        return text_lower in single_word_commands
    
    # Filter out common noise/gibberish patterns
    noise_patterns = [
        'uh', 'um', 'hmm', 'ah', 'oh', 'eh',
        'cough', 'sneeze', 'ahem',
        'la', 'na', 'ha', 'he', 'ho'
    ]
    
    # If all words are noise, ignore
    if all(word in noise_patterns for word in words):
        return False
    
    # Check for meaningful keywords (commands, questions, statements)
    meaningful_keywords = [
        # English
        'how', 'what', 'when', 'where', 'who', 'why', 'which',
        'open', 'close', 'start', 'stop', 'play', 'pause',
        'hello', 'hi', 'bye', 'goodbye', 'thanks', 'thank',
        'are', 'is', 'can', 'could', 'will', 'would',
        'your', 'my', 'name', 'you', 'me',
        
        # Hindi/Hinglish
        'kya', 'kaise', 'kab', 'kahan', 'kaun', 'kyon',
        'karo', 'band', 'ruk', 'chalo', 'suno',
        'namaste', 'tum', 'aap', 'mera', 'tumhara',
        'hai', 'ho', 'hoon', 'hain',
        'theek', 'accha', 'bura', 'sahi'
    ]
    
    # If text contains at least one meaningful keyword, it's valid
    for keyword in meaningful_keywords:
        if keyword in text_lower:
            return True
    
    # If we reach here, it's probably gibberish or noise
    return False
