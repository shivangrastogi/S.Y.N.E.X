import os
import pygame
import random
import threading
from pygame import mixer

from FUNCTION.CLAP_DETECTOR.clapd import TapTester
from FUNCTION.JARVIS_SPEAK.speak import speak
from FUNCTION.JARVIS_LISTEN.listen import listen  # Your voice rec function

# ==== INITIALIZE pygame/mixer ONCE ONLY ====
pygame.init()
mixer.init()

is_playing = False
music_mode_active = True
music_lock = threading.Lock()

playlist = []
current_index = -1

def build_playlist(music_folder):
    # List all music files and remember the order for prev/next
    files = sorted([f for f in os.listdir(music_folder) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))])
    return files

def play_song(music_folder, index):
    global is_playing
    song_name = playlist[index]
    music_path = os.path.join(music_folder, song_name)
    try:
        mixer.music.load(music_path)
        mixer.music.play()
        is_playing = True
        speak(f"Now playing {song_name.rsplit('.', 1)[0]}")
        print(f"[JARVIS] 🎵 Playing: {song_name}")
    except Exception as e:
        speak("Unable to play music.")
        print(f"Music error: {e}")
        is_playing = False

def play_random_music(music_folder):
    global is_playing, current_index
    with music_lock:
        if is_playing:
            return
        if not playlist:
            speak("No music files found, sir.")
            return
        current_index = random.randint(0, len(playlist)-1)
        play_song(music_folder, current_index)
    while music_mode_active and is_playing and mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    with music_lock:
        mixer.music.stop()
        is_playing = False

def play_next_song(music_folder):
    global current_index
    with music_lock:
        if not playlist:
            speak("No next song, sir.")
            return
        current_index = (current_index + 1) % len(playlist)
        play_song(music_folder, current_index)

def play_previous_song(music_folder):
    global current_index
    with music_lock:
        if not playlist:
            speak("No previous song, sir.")
            return
        current_index = (current_index - 1) % len(playlist)
        play_song(music_folder, current_index)

def pause_or_resume_music():
    if mixer.music.get_busy():
        if mixer.music.get_pos() > 0 and not mixer.music.get_busy():
            mixer.music.unpause()
            speak("Resuming the music.")
        else:
            mixer.music.pause()
            speak("Music paused.")
    else:
        mixer.music.unpause()
        speak("Resuming the music.")

def handle_voice_command(command, music_folder):
    global is_playing, music_mode_active
    cmd = command.lower()
    if "stop music" in cmd:
        speak("Stopping the music.")
        with music_lock:
            mixer.music.stop()
            is_playing = False
            music_mode_active = False
    elif "stop" in cmd:
        with music_lock:
            if is_playing:
                mixer.music.pause()
                speak("Music paused.")
    elif "play" in cmd or "resume" in cmd:
        with music_lock:
            if not is_playing:
                mixer.music.unpause()
                speak("Resuming the music.")
                is_playing = True
    elif "next" in cmd:
        speak("Playing next song.")
        play_next_song(music_folder)
    elif "previous" in cmd or "prev" in cmd:
        speak("Playing previous song.")
        play_previous_song(music_folder)
    else:
        speak("Command not recognized for music.")

def listen_for_music_commands(music_folder):
    global is_playing, music_mode_active
    while music_mode_active:
        if is_playing:
            command = listen().lower()
            print(f"[JARVIS] Heard: {command}")
            handle_voice_command(command, music_folder)

def clap_to_music():
    global playlist, is_playing, music_mode_active, current_index
    base_dir = os.path.dirname(os.path.abspath(__file__))
    music_folder_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'DATA', 'MUSIC'))

    playlist = build_playlist(music_folder_path)
    current_index = -1
    is_playing = False
    music_mode_active = True

    speak("Clap to start music, say play, stop, next, previous, or stop music to exit.")

    tt = TapTester()
    stop_listener = threading.Thread(target=listen_for_music_commands, args=(music_folder_path,), daemon=True)
    stop_listener.start()

    while music_mode_active:
        if not is_playing and tt.listen() and music_mode_active:
            # Play random or next song on clap
            threading.Thread(target=play_random_music, args=(music_folder_path,)).start()

    print("[JARVIS] Music mode exited.")


# import os
# import pygame
# import random
# import threading
# from pygame import mixer
#
# from FUNCTION.CLAP_DETECTOR.clapd import TapTester
# from FUNCTION.JARVIS_SPEAK.speak import speak
# from FUNCTION.JARVIS_LISTEN.listen import listen  # Your voice recognition function
#
# # Initialize pygame/mixer ONCE
# pygame.init()
# mixer.init()
#
# is_playing = False
# music_mode_active = True  # This flag disables music mode after "stop music"
# music_lock = threading.Lock()
#
# def play_random_music(folder_path):
#     global is_playing
#     with music_lock:
#         if is_playing:
#             return
#         music_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))]
#         if not music_files:
#             speak("No music files found, sir.")
#             return
#
#         selected_music = random.choice(music_files)
#         music_path = os.path.join(folder_path, selected_music)
#         try:
#             mixer.music.load(music_path)
#             mixer.music.play()
#             is_playing = True
#             speak(f"Now playing {selected_music.rsplit('.',1)[0]}")
#             print(f"[JARVIS] 🎵 Playing: {selected_music}")
#         except Exception as e:
#             speak("Unable to play music.")
#             print(f"[JARVIS] Music error: {e}")
#             is_playing = False
#             return
#
#     while music_mode_active and is_playing and mixer.music.get_busy():
#         pygame.time.Clock().tick(10)
#     with music_lock:
#         mixer.music.stop()
#         is_playing = False
#
# def listen_for_stop_music():
#     global is_playing, music_mode_active
#     while music_mode_active:
#         if is_playing:
#             command = listen().lower()
#             print(f"[JARVIS] Heard: {command}")
#             if "stop music" in command:
#                 speak("Stopping the music.")
#                 with music_lock:
#                     mixer.music.stop()
#                     is_playing = False
#                     music_mode_active = False  # Exit the music mode
#
# def clap_to_music():
#     global music_mode_active
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     music_folder_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'DATA', 'MUSIC'))
#
#     speak("Clap to start the music, and say stop music to stop it.")
#     tt = TapTester()
#
#     stop_listener = threading.Thread(target=listen_for_stop_music, daemon=True)
#     stop_listener.start()
#
#     while music_mode_active:
#         if not is_playing and tt.listen():
#             # Re-check the flag in case user said stop while tt.listen was waiting
#             if music_mode_active:
#                 music_thread = threading.Thread(target=play_random_music, args=(music_folder_path,))
#                 music_thread.start()
#
#     print("[JARVIS] Music mode exited.")
#
# if __name__ == "__main__":
#     clap_to_music()


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
