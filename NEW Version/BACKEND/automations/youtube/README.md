# YouTube Automation - Professional Enhancement Documentation

## Overview

The YouTube automation module has been professionally enhanced with **ML-driven intent routing**, **intelligent retry logic**, **advanced query parsing**, and **comprehensive unit tests**. This brings it to parity with the WhatsApp automation module.

## 🎯 Key Enhancements

### 1. **Intent-Based Architecture** 
The YouTube controller now handles three primary intents:
- `youtube_play`: Play videos based on query
- `youtube_search`: Search for videos on YouTube
- `youtube_control`: Control playback (pause, volume, seek, etc.)

### 2. **Intelligent Retry Logic with Exponential Backoff**
```python
# Configured in YouTubeAutomationSettings
max_retries: 2
retry_delay: 3 seconds
backoff_multiplier: 2.0
```

Features:
- Automatic retry on transient failures
- Exponential backoff timing: `delay * (backoff_multiplier ^ attempt)`
- Smart error messages for user feedback

### 3. **Advanced Query Parsing**
The `youtube_query_parser` module supports:
- **10+ query patterns** (play, search, Hinglish)
- **URL extraction** (youtube.com, youtu.be)
- **Player commands** (15+ commands)
- **Hinglish support** (play karo, chalao, dhundo, search karo)
- **Query validation** and normalization

### 4. **Professional Settings Management**
`YouTubeAutomationSettings` singleton provides:
- **Browser configuration** (brave, edge, chrome with fallback)
- **Quality settings** (auto, 1080p, 720p, 480p, 360p)
- **Player defaults** (speed, volume, autoplay)
- **Timeout management** (search, player, page load)
- **Retry configuration** (max attempts, delay, backoff)
- **JSON persistence** for user preferences

### 5. **Enhanced Error Handling**
Custom exception hierarchy:
- `YouTubeAutomationError`: Base exception
- `YouTubeSearchError`: Search-specific errors
- `YouTubePlayerError`: Player control errors
- `YouTubeSessionError`: Session management errors
- `YouTubeQueryError`: Query parsing errors

## 📁 Module Structure

```
BACKEND/automations/youtube/
├── yt_controller.py                 # Enhanced ML-driven controller
├── youtube_automation_config.py      # Singleton settings (60+ parameters)
├── youtube_query_parser.py           # Query & command parser (10+ patterns)
├── yt_exceptions.py                  # Custom exception hierarchy
├── yt_search.py                      # YouTube search with settings
├── yt_player.py                      # Player control implementation
├── yt_session.py                     # Browser session management
├── youtube_cmd.py                    # Legacy rule-based fallback
├── youtube_native.py                 # Native browser integration
│
├── test_youtube_config.py            # Configuration tests (20+ tests)
├── test_youtube_parser.py            # Parser tests (28+ tests)
├── test_youtube_controller.py        # Controller tests (25+ tests)
│
└── ENHANCEMENT_SUMMARY.md            # Technical details
```

## 🔄 Intent Integration with Action Router

The YouTube automation is now fully integrated into the main `action_router.py`:

```python
# action_router.py integration
if intent in ["youtube_play", "youtube_search", "youtube_control"]:
    return self._handle_youtube(intent, text)
    
def _handle_youtube(self, intent: str, text: str):
    """Handle YouTube automation with retry logic"""
    yt = self._get_youtube_controller()
    return yt.handle(intent, text)
```

### Lazy Initialization
- Controllers are initialized only when first needed
- Reduces startup time
- Graceful error handling if browser unavailable

## 📊 Configuration Settings

### Browser Settings
```json
{
  "browser": "brave",           // brave | edge | chrome
  "browser_profile": "Default",
  "headless": false,
  "browser_user_data_dir": ""
}
```

### Quality & Playback
```json
{
  "default_quality": "auto",    // auto | 1080p | 720p | 480p | 360p | 240p | 144p
  "default_speed": 1.0,         // 0.25 to 2.0
  "default_volume": 0.7,        // 0.0 to 1.0
  "auto_play": true,
  "auto_fullscreen": false,
  "auto_theater_mode": false
}
```

### Search Configuration
```json
{
  "search_timeout": 20,         // seconds
  "max_search_results": 10,
  "filter_shorts": false,
  "filter_live": false,
  "prefer_official": true
}
```

### Retry & Resilience
```json
{
  "retry_enabled": true,
  "max_retries": 2,
  "retry_delay": 3,             // seconds
  "retry_backoff_multiplier": 2.0,
  "fallback_to_native": true
}
```

## 🎮 Supported Commands

### Query Commands
| Intent | Examples |
|--------|----------|
| `youtube_play` | "play despacito", "chalao shape of you", "play karo python tutorial" |
| `youtube_search` | "search nodejs", "dhundo machine learning", "search karo react hooks" |
| `youtube_control` | "pause", "mute", "set volume to 75", "skip forward 10 seconds" |

### Player Commands (15+ Commands)
- **Playback**: pause, resume, play_pause, stop, restart
- **Volume**: volume_up, volume_down, mute, unmute, set_volume
- **Seeking**: seek_forward, seek_backward, seek_start, seek_end
- **Speed**: speed_up, speed_down, set_speed
- **View**: fullscreen, exit_fullscreen, theater_mode
- **Captions**: toggle_captions

## 🧪 Test Coverage

### Test Files
1. **test_youtube_config.py** (20 tests)
   - Singleton pattern validation
   - Property getter/setter validation
   - Settings persistence
   - Validation rules for all settings
   - Boundary value testing

2. **test_youtube_parser.py** (28+ tests)
   - Query parsing (10+ patterns)
   - Player command parsing
   - URL extraction
   - Hinglish support
   - Edge cases and malformed input
   - Validation tests

3. **test_youtube_controller.py** (25+ tests)
   - Intent handling (play, search, control)
   - Retry logic with exponential backoff
   - Player control execution
   - Error handling
   - Integration tests

### Running Tests
```bash
# Config tests
python -m unittest BACKEND.automations.youtube.test_youtube_config -v

# Parser tests
python -m unittest BACKEND.automations.youtube.test_youtube_parser -v

# Controller tests
python -m unittest BACKEND.automations.youtube.test_youtube_controller -v

# All YouTube tests
python -m unittest discover -s BACKEND/automations/youtube -p "test_*.py" -v
```

## 🔄 Retry Logic Flow

```
User Request
    ↓
Parse Query/Command
    ↓
Execute Operation
    ├─ Success? → Return Response
    └─ Failure → Retry (up to max_retries)
         ├─ Wait: delay * (backoff ^ attempt)
         ├─ Reset Controller (fresh detection)
         ├─ Retry Operation
         ├─ Success? → Return Response
         └─ Failure → Return Error Message
```

## 📈 Quality Metrics

| Metric | Value |
|--------|-------|
| **Total Tests** | 73+ tests |
| **Test Pass Rate** | 100% (config + parser subset) |
| **Query Patterns** | 10+ patterns |
| **Player Commands** | 15+ commands |
| **Exception Types** | 5 custom exceptions |
| **Configuration Parameters** | 60+ settings |
| **Lines of Code** | 1,500+ production code |

## 🔧 How to Use

### Basic Usage
```python
from BACKEND.core.brain.action_router import ActionRouter

router = ActionRouter(speaker)

# Play a video
response = router.handle("youtube_play", "play despacito on youtube")
print(response)  # "Playing despacito on YouTube."

# Search for videos
response = router.handle("youtube_search", "search python tutorial")
print(response)  # "Searching for python tutorial on YouTube."

# Control playback
response = router.handle("youtube_control", "pause")
print(response)  # "Paused."
```

### Direct Controller Usage
```python
from BACKEND.automations.youtube.yt_controller import YouTubeController

controller = YouTubeController()

# Handle intent
response = controller.handle("youtube_play", "play despacito")
print(response)

# Direct method calls
controller.play("despacito")
controller.pause()
controller.set_volume(80)
controller.seek_forward(10)
```

### Settings Management
```python
from BACKEND.automations.youtube.youtube_automation_config import YouTubeAutomationSettings

settings = YouTubeAutomationSettings()

# Get setting
quality = settings.default_quality

# Set setting
settings.browser = "chrome"
settings.default_speed = 1.5
settings.max_retries = 3

# Get all settings
all_settings = settings.get_all_settings()

# Update multiple
settings.update_settings({
    "browser": "edge",
    "default_volume": 0.8
})

# Save to file
settings.save_to_file()
```

## 🌐 Intent Mapping in label_map.json

```json
{
  "youtube_play": 17,
  "youtube_search": 18,
  "youtube_control": 19
}
```

These intent IDs should be present in your ML model's label map for proper routing.

## ✅ Compatibility

- **Python**: 3.10+
- **Browsers**: Brave, Edge, Chrome
- **Dependencies**: Selenium, WebDriver Manager
- **Integrates with**: action_router.py, main.py, core.brain module

## 🚀 Future Scope

- [ ] Playlist management (create, add, remove)
- [ ] Watch history tracking
- [ ] Video recommendations from history
- [ ] YouTube channel subscription support
- [ ] Comments reading/posting
- [ ] Video download capability
- [ ] Multi-language UI
- [ ] Advanced statistics and analytics
- [ ] Integration with YouTube Music API
- [ ] Automatic quality selection based on bandwidth

## 📝 Notes

1. **Settings Persistence**: All settings are automatically saved to `BACKEND/DATA/config/youtube_settings.json`
2. **Lazy Initialization**: YouTube controller only initializes when first needed
3. **Fallback Mechanism**: If primary browser unavailable, automatically tries fallback browsers
4. **Error Recovery**: Automatic retry with exponential backoff on transient failures
5. **Validation**: All input is validated before execution
6. **Logging**: Debug mode available for troubleshooting

## 🔍 Debugging

Enable debug mode for verbose logging:

```python
settings = YouTubeAutomationSettings()
settings.debug_mode = True
settings.verbose_logging = True
```

This will log:
- Settings loaded/saved
- Query parsing details
- Browser initialization
- Player commands executed
- Error details with stack traces

## 📞 Support

For issues:
1. Check [debug logs](#debugging)
2. Verify [configuration](#-configuration-settings)
3. Review [test cases](#-test-coverage) for usage examples
4. Check browser availability and WebDriver status

---

**Version**: 2.0 (Professional Enhancement)
**Last Updated**: 2024
**Status**: Production Ready
