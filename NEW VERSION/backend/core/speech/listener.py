# Path: d:\New folder (2) - JARVIS\backend\core\speech\listener.py
"""
Listener Module - Speech-to-Text Engine
Handles speech recognition using Google Speech Recognition.
"""

import speech_recognition as sr


class ListenEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Disable dynamic threshold - we'll use a fixed higher threshold
        self.recognizer.dynamic_energy_threshold = False
        # Much higher threshold to avoid ambient noise
        self.recognizer.energy_threshold = 1000
        # Adjust pause threshold for better speech detection
        self.recognizer.pause_threshold = 0.8  # Seconds of silence to consider phrase complete
        self.microphone = None
        
    def start_listening(self):
        """
        Starts continuous listening mode with persistent microphone connection.
        """
        if self.microphone is None:
            self.microphone = sr.Microphone()
            self.microphone.__enter__()
            # One-time calibration
            print("Calibrating microphone...")
            self.recognizer.adjust_for_ambient_noise(self.microphone, duration=0.5)
            print("Ready! Listening continuously...")
    
    def stop_listening(self):
        """
        Stops continuous listening and releases microphone.
        """
        if self.microphone:
            try:
                self.microphone.__exit__(None, None, None)
            except Exception as e:
                print(f"Error releasing microphone: {e}")
            finally:
                self.microphone = None
    
    def listen(self):
        """
        Listens for speech input using the persistent microphone connection.
        Returns recognized text or None if no speech detected.
        """
        if self.microphone is None:
            return None  # Microphone not active, return silently
        
        try:
            # Add a small timeout (e.g. 1 second) to allow the loop to check self.running regularly
            # phrase_time_limit ensures we don't wait forever for a single phrase
            audio = self.recognizer.listen(self.microphone, timeout=1, phrase_time_limit=10)

        except sr.WaitTimeoutError:
            # Silence timeout errors as requested by user
            return None
        except OSError as e:
            # Stream errors (closed/stopped) - microphone was released
            if "Stream" in str(e):
                return None  # Silently return, mic was turned off
            print(f"Listening error: {e}")
            return None
        except Exception as e:
            # Only print if it's not a stream error or timeout
            # We are silencing almost everything to avoid console flooding as requested
            err_str = str(e).lower()
            if "stream" not in err_str and "timed out" not in err_str and "listening timed out" not in err_str:
                 # Only print real errors
                 print(f"Listening error: {e}")
            return None

        # Check if audio has sufficient energy (not just ambient noise)
        try:
            import audioop
            # Calculate RMS (root mean square) of audio to check volume
            rms = audioop.rms(audio.get_raw_data(), audio.sample_width)
            
            # If RMS is too low, it's probably just ambient noise - skip recognition
            if rms < 500:  # Threshold for minimum audio energy
                return None
                
        except Exception:
            # If we can't check audio energy, proceed with recognition anyway
            pass

        # Only attempt recognition if we have meaningful audio
        try:
            # Recognize speech using Google Speech Recognition (silently)
            # 'en-IN' (Indian English) captures Indian accents and common Hindi words in Latin script well.
            text = self.recognizer.recognize_google(audio, language='en-IN')
            print(f"Recognized: {text}")
            return text
        except sr.UnknownValueError:
            # Audio was captured but couldn't be understood - return silently
            return None
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            return None

