[//]: # (Path: d:\New folder (2) - JARVIS\README.md)
# JARVIS 2.0 - System Interaction Walkthrough

## 1. Overview
The JARVIS 2.0 architecture cleanly separates the User Interface (PyQt6) from the Backend Services (Synex, Automations). This ensures stability, ease of maintenance, and scalability.

## 2. Project Structure
- **Root Directory**: `d:/New folder (2) - JARVIS/`
    - `ui_laptop/`: Contains all Frontend UI code.
        - `main.py`: Entry point for the application.
        - `voice_input.py`: Manages microphone UI and user input signals.
    - `backend/`: Contains all core logic.
        - `main.py`: The `Synex` class, serving as the bridge between UI and Core logic.
        - `core/`: Speech recognition (`listener.py`), TTS (`speaker.py`), and Language processing.
        - `automations/`: Specialized modules for YouTube, Google, WhatsApp, etc.
        - `command_processor.py`: Central router that dispatches user text to appropriate automations.

## 3. Key Features
- **Immediate Listening**: The system automatically starts listening for voice commands upon launch.
- **Robust UI Signals**: User interactions (Mic toggle, Send button) are safely connected to the backend via PyQt signals, preventing crashes.
- **Unified Command Processing**: All inputs (Voice or Text) are routed through `CommandProcessor`, which intelligently dispatches them to:
    - **YouTube Controller**: For playing videos and controlling playback.
    - **Google Controller**: For web searches and browser navigation.
    - **WhatsApp Controller**: For messaging.
    - **System Commands**: For shutdown, greetings, etc.

## 4. How to Run
1. Activate the virtual environment:
   ```powershell
   .venv\Scripts\Activate
   ```
2. Run the UI application:
   ```powershell
   python ui_laptop/main.py
   ```

## 5. Usage Examples
- **YouTube**: "Play Despacito on YouTube", "Search for Python tutorials".
- **Browser**: "Search Google for AI news", "Open StackOverflow".
- **WhatsApp**: "WhatsApp send message to Mom".
- **System**: "Shutdown", "Exit", "Hello".

## 6. Troubleshooting
- If dependencies are missing, ensure you have installed:
  `selenium`, `webdriver_manager`, `edge-tts`, `SpeechRecognition`, `psutil`, `pyautogui`, `vosk`.
- Check `backend/logs` (if configured) for detailed error traces.
