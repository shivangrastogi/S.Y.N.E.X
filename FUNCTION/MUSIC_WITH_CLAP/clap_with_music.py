import os
import pygame
import random
import threading
from pygame import mixer

from FUNCTION.CLAP_DETECTOR.clapd import TapTester
from FUNCTION.JARVIS_SPEAK.speak import speak
from FUNCTION.JARVIS_LISTEN.listen import listen  # Assumes you have a voice listening function

# Shared flag to control music
is_playing = False

def play_random_music(folder_path):
    global is_playing

    music_files = [file for file in os.listdir(folder_path) if file.endswith(('.mp3', '.wav', '.ogg', '.flac'))]
    if not music_files:
        speak("No music files found, sir.")
        return

    selected_music = random.choice(music_files)
    music_path = os.path.join(folder_path, selected_music)

    try:
        pygame.init()
        mixer.init()
        mixer.music.load(music_path)
        mixer.music.play()
        is_playing = True
        speak(f"Now playing {selected_music.split('.')[0]}")
        print(f"[JARVIS] 🎵 Playing: {selected_music}")

        while is_playing and mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        mixer.music.stop()
        mixer.quit()
        is_playing = False
    except Exception as e:
        speak("Unable to play music.")
        print(f"[JARVIS] Music error: {e}")

def listen_for_stop_music():
    global is_playing
    while True:
        if is_playing:
            command = listen().lower()
            print(f"[JARVIS] Heard: {command}")
            if "stop music" in command:
                speak("Stopping the music.")
                mixer.music.stop()
                mixer.quit()
                is_playing = False

def clap_to_music():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    music_folder_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'DATA', 'MUSIC'))

    speak("Clap to start the music, and say stop music to stop it.")
    tt = TapTester()

    # Start the listener thread once
    stop_listener = threading.Thread(target=listen_for_stop_music, daemon=True)
    stop_listener.start()

    while True:
        if not is_playing and tt.listen():
            music_thread = threading.Thread(target=play_random_music, args=(music_folder_path,))
            music_thread.start()


#
# import os
# import pygame
# import random
# from pygame import mixer
# from FUNCTION.CLAP_DETECTOR.clapd import *
# from playsound import playsound
# from FUNCTION.JARVIS_SPEAK.speak import *
#
#
# def play_random_music(folder_path):
#     music_files = [file for file in os.listdir(folder_path) if file.endswith(('.mp3', '.wav', '.ogg', '.flac'))]
#
#     if not music_files:
#         print("No music files found in the specified folder.")
#         return
#
#     selected_music = random.choice(music_files)
#     music_path = os.path.join(folder_path, selected_music)
#
#     try:
#         # Initialize pygame and mixer
#         pygame.init()
#         mixer.init()
#
#         # Load and play the selected music file in the background
#         mixer.music.load(music_path)
#         mixer.music.play()
#
#         # Wait for the music to finish (or you can add some delay or user input here)
#         while pygame.mixer.music.get_busy():
#             pygame.time.Clock().tick(10)  # Adjust the tick value as needed
#
#         # Stop and quit pygame mixer
#         mixer.music.stop()
#         mixer.quit()
#     except Exception as e:
#         print(f"Error playing music: {e}")
#
#
# def clap_to_music():
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     music_folder_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'DATA', 'MUSIC'))
#     while True:
#         tt = TapTester()
#         clap_count = 0
#
#         while True:
#             if tt.listen():
#                 clap_count += 2
#                 print("playing.. music sir")
#                 play_random_music(music_folder_path)
#                 # play_random_music(
#                 #     r"C:\Users\bosss\Desktop\JARVIS\DATA\MUSIC")
#
#                 if clap_count == REQUIRED_CLAPS:
#                     break
