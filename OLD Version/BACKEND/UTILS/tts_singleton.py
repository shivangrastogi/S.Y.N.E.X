#tts_singleton.py

from FUNCTION.SPEAK.speak import JarvisSpeaker

# Create a single JarvisSpeaker instance at module load (model loaded once)
jarvis_instance = JarvisSpeaker()

# Expose the speak method to import directly
speak = jarvis_instance.speak
