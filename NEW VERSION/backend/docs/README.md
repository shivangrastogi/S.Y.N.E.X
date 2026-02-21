[//]: # (Path: d:\New folder (2) - JARVIS\backend\docs\README.md)
# JARVIS - Voice Assistant

A bilingual (Hindi/English) voice assistant with modular architecture for easy expansion.

## Features

- **Speech Recognition**: Understands both Hindi and English (Hinglish)
- **Text-to-Speech**: Natural-sounding male voices for both languages
- **Fast Response**: Optimized for minimal latency between listening and speaking
- **Modular Architecture**: Clean separation of concerns for easy maintenance

## Project Structure

```
JARVIS/
├── main.py                    # Entry point (ONLY file in root)
├── config/                    # Configuration files
│   └── requirements.txt       # Dependencies
├── docs/                      # Documentation
│   └── README.md             # This file
├── core/                      # Core voice assistant functionality
│   ├── speech/               # Speech-related modules
│   │   ├── listener.py       # Speech-to-text (STT)
│   │   └── speaker.py        # Text-to-speech (TTS)
│   └── language/             # Language processing
│       └── detector.py       # Language detection
├── automation/               # Future: Task automation
├── brain/                    # Future: AI/NLP processing
└── utils/                    # Utilities & configuration
```

## Installation

1. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r config/requirements.txt
```

## Usage

Run the assistant:
```bash
python main.py
```

### Commands

**English:**
- "Hello, how are you?"
- "What is your name?"

**Hindi/Hinglish:**
- "Namaste"
- "Tum kaise ho?"
- "Tumhara naam kya hai?"

**Exit:**
- "Exit" / "Stop" / "Ruk jao" / "Band karo"

## Technical Details

- **STT**: Google Speech Recognition with `en-IN` model
- **TTS**: Microsoft Edge TTS (`hi-IN-MadhurNeural`, `en-US-ChristopherNeural`)
- **Language Detection**: Keyword-based Hindi/English detection

## Future Enhancements

- **Automation**: System control, app launching, file management
- **Brain**: Context-aware responses, NLP, memory
- **Utilities**: Configuration management, logging, error handling
