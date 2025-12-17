# build.py
import PyInstaller.__main__
import os
import sys
import shutil

# --- CONFIGURATION ---
# 1. The Entry Point: Your UI File
ENTRY_POINT = os.path.join("PC SOFTWARE", "GUI_MAKING", "NEW_UI", "main.py")

# 2. Name of your EXE
APP_NAME = "JARVIS_AI"

# 3. Paths to your folders
BASE_DIR = os.path.abspath(".")
DATA_DIR = os.path.join(BASE_DIR, "DATA")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")  # If you have images/gifs here

# 4. NLU Model Path (CRITICAL)
# We need to find where 'en_core_web_sm' or your custom model is installed
import spacy

try:
    # Use your custom model path if you have one, otherwise fall back to standard
    # This logic tries to find the actual folder path of the spacy model to bundle it
    nlp = spacy.load("en_core_web_sm")
    SPACY_MODEL_PATH = nlp._path
    print(f"✅ Found SpaCy model at: {SPACY_MODEL_PATH}")
except:
    print("⚠️ Warning: Could not auto-detect spaCy model. You might need to manually set SPACY_MODEL_PATH.")
    SPACY_MODEL_PATH = None


# --- UTILITY: Get PyInstaller Data Format ---
def get_data_tuple(source, dest):
    # PyInstaller expects 'SourcePath;DestPath' for Windows
    return f"{source}{os.pathsep}{dest}"


# --- BUILD COMMAND ARGS ---
args = [
    ENTRY_POINT,  # Script to run
    f'--name={APP_NAME}',  # Name of exe
    '--noconfirm',  # Replace output directory without asking
    '--windowed',  # No Black Console Window (GUI mode)
    '--clean',  # Clean cache

    # --- PATHS ---
    # Add the root folder to python path so 'import MAIN...' works
    f'--paths={BASE_DIR}',

    # --- DATA FILES (The most important part) ---
    # 1. DATA Folder (Memory, Models, Keys) -> Placed in 'DATA' inside exe
    f'--add-data={get_data_tuple(DATA_DIR, "DATA")}',

    # 2. ASSETS Folder (Images, GIFs for UI) -> Placed in 'assets' inside exe
    f'--add-data={get_data_tuple(ASSETS_DIR, "assets")}',

    # 3. FIREBASE KEY (Explicitly add if inside DATA/FIREBASE)
    # (Already covered by adding entire DATA folder, but good to be safe if outside)

    # --- HIDDEN IMPORTS ---
    # Libraries that PyInstaller often misses
    '--hidden-import=pyttsx3.drivers',
    '--hidden-import=pyttsx3.drivers.sapi5',
    '--hidden-import=spacy',
    '--hidden-import=thinc',
    '--hidden-import=cymem',
    '--hidden-import=preshed',
    '--hidden-import=blis',
    '--hidden-import=murmurhash',
    '--hidden-import=firebase_admin',
    '--hidden-import=firebase_admin.firestore',
    '--hidden-import=engineio.async_drivers.threading',  # Common socketio/firebase issue
    '--hidden-import=dns',  # Often needed for Firebase connection
    '--hidden-import=psutil',

    # --- EXCLUDES (Save Size) ---
    '--exclude-module=tkinter',
    '--exclude-module=matplotlib',
    '--exclude-module=notebook',
    '--exclude-module=scipy',
    '--exclude-module=pandas',  # Unless you used it explicitly
]

# Add SpaCy Model if found
if SPACY_MODEL_PATH:
    # Bundle the model folder into the internal spacy data directory
    # The destination must match what spacy expects internally or we load it via path
    # Simpler approach: Put it in a folder named 'en_core_web_sm' at root of exe
    args.append(f'--add-data={get_data_tuple(SPACY_MODEL_PATH, "en_core_web_sm")}')

# --- RUN BUILD ---
print("🚀 Starting PyInstaller Build...")
print(f"   Entry Point: {ENTRY_POINT}")
PyInstaller.__main__.run(args)
print("✅ Build Complete. Check the 'dist' folder.")