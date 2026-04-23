import re

class HinglishNormalizer:
    def __init__(self):
        # Dictionary for Hinglish to English mapping
        self.translation_map = {
            "kholo": "open",
            "chalu": "open",
            "start": "open",
            "launch": "open",
            "band": "close",
            "hatao": "close",
            "rok": "stop",
            "batao": "tell",
            "dikhao": "show",
            "sunao": "play",
            "gana": "music",
            "mausam": "weather"
        }
        
        # Filler words to remove
        self.fillers = [
            "bhai", "yaar", "please", "zara", "ek", "thoda", "kar", "de", 
            "do", "karo", "kardo", "karna", "hai", "tha", "raha", "o"
        ]

    def normalize(self, text):
        if not text:
            return ""
            
        text = text.lower().strip()
        
        # Remove special characters
        text = re.sub(r'[^\w\s]', '', text)
        
        words = text.split()
        cleaned_words = []
        
        for word in words:
            # 1. Translate if it's in our map
            if word in self.translation_map:
                cleaned_words.append(self.translation_map[word])
            # 2. Skip if it's a filler
            elif word in self.fillers:
                continue
            # 3. Keep the word as is
            else:
                cleaned_words.append(word)
                
        return " ".join(cleaned_words)

if __name__ == "__main__":
    normalizer = HinglishNormalizer()
    test_cases = [
        "bhai chrome open kar de",
        "chrome kholo",
        "notepad band karo please",
        "weather batao"
    ]
    
    for tc in test_cases:
        print(f"Original: {tc} -> Normalized: {normalizer.normalize(tc)}")
