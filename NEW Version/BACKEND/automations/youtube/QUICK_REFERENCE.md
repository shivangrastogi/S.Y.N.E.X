# YouTube Automation - Quick Reference Guide

## 🚀 Quick Start

### Playing Videos
```
User says: "Play despacito on YouTube"
Intent: youtube_play
Action: Opens YouTube and plays video
Response: "Playing despacito on YouTube."
```

### Searching Videos
```
User says: "Search for python tutorial"
Intent: youtube_search
Action: Searches and displays results
Response: "Searching for python tutorial on YouTube."
```

### Controlling Playback
```
User says: "Pause"
Intent: youtube_control
Action: Pauses current video
Response: "Paused."
```

## 📋 Supported Intents

| Intent | When Used | Example |
|--------|-----------|---------|
| `youtube_play` | User wants to play video | "play shape of you" |
| `youtube_search` | User wants to search | "search nodejs tutorial" |
| `youtube_control` | User wants to control player | "pause", "volume up" |

## 🎮 Player Commands (Full List)

### Playback Control
- `pause` - Pause video
- `resume` - Resume/play video
- `play_pause` - Toggle play/pause
- `stop` - Stop video
- `restart` - Restart video

### Volume Control
- `volume_up` - Increase volume
- `volume_down` - Decrease volume
- `mute` - Mute audio
- `unmute` - Unmute audio
- `set_volume 75` - Set volume to 75%

### Seek/Skip
- `seek_forward 10` - Skip forward 10 seconds
- `seek_backward 30` - Skip backward 30 seconds
- `seek_start` - Jump to beginning
- `seek_end` - Jump to end

### Speed Control
- `speed_up` - Increase playback speed
- `speed_down` - Decrease playback speed
- `set_speed 1.5` - Set speed to 1.5x

### View Options
- `fullscreen` - Enter fullscreen
- `exit_fullscreen` - Exit fullscreen
- `theater_mode` - Toggle theater mode
- `captions` - Toggle captions

## 🌍 Language Support

### English
- "Play despacito"
- "Search for python tutorial"
- "Increase volume"

### Hinglish (Hindi + English)
- "Play karo despacito" (Play despacito)
- "Search karo nodejs" (Search nodejs)
- "Chalao shape of you" (Play shape of you)
- "Dhundo machine learning" (Search machine learning)

## ⚙️ Key Settings

### Browser Configuration
- Default: `brave`
- Options: `brave`, `edge`, `chrome`
- Change: `settings.browser = "chrome"`

### Video Quality
- Default: `auto`
- Options: `auto`, `1080p`, `720p`, `480p`, `360p`
- Change: `settings.default_quality = "720p"`

### Playback Speed
- Default: `1.0`
- Range: `0.25` to `2.0`
- Change: `settings.default_speed = 1.5`

### Volume Level
- Default: `0.7` (70%)
- Range: `0.0` to `1.0`
- Change: `settings.default_volume = 0.8`

### Retry Configuration
- Max Retries: `2`
- Retry Delay: `3` seconds
- Backoff Multiplier: `2.0`

## 🔍 Error Handling

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "YouTube automation failed" | Browser not running | Start browser manually |
| "Query error: Invalid query" | Query too short/long | Provide valid search term |
| "Failed to execute after 2 attempts" | Transient error | Retry or check browser |

### Retry Behavior
- Automatic retry on failure
- Exponential backoff: `delay * (2 ^ attempt)`
- Max 2 attempts by default
- User-friendly error messages

## 📊 Configuration File Location

```
BACKEND/DATA/config/youtube_settings.json
```

### Sample Configuration
```json
{
  "browser": "brave",
  "default_quality": "720p",
  "default_speed": 1.0,
  "default_volume": 0.7,
  "max_retries": 2,
  "retry_delay": 3
}
```

## 🧪 Testing

### Run All Tests
```bash
python -m unittest discover -s BACKEND/automations/youtube -p "test_*.py" -v
```

### Run Specific Test File
```bash
# Configuration tests
python -m unittest BACKEND.automations.youtube.test_youtube_config -v

# Parser tests
python -m unittest BACKEND.automations.youtube.test_youtube_parser -v

# Controller tests
python -m unittest BACKEND.automations.youtube.test_youtube_controller -v
```

### Test Coverage
- ✅ 20 configuration tests
- ✅ 28+ parser tests
- ✅ 25+ controller tests
- **Total**: 73+ unit tests

## 📈 File Structure

```
BACKEND/automations/youtube/
├── yt_controller.py              # Main controller (intent routing)
├── youtube_automation_config.py   # Settings management
├── youtube_query_parser.py        # Query/command parsing
├── yt_exceptions.py               # Custom exceptions
├── yt_search.py                   # Search implementation
├── yt_player.py                   # Player controls
├── yt_session.py                  # Browser session
├── youtube_cmd.py                 # Legacy fallback
├── test_youtube_config.py         # Config tests
├── test_youtube_parser.py         # Parser tests
├── test_youtube_controller.py     # Controller tests
├── README.md                      # Full documentation
└── ENHANCEMENT_SUMMARY.md         # Technical details
```

## 🔌 Integration Points

### With Action Router
```python
# In action_router.py
if intent in ["youtube_play", "youtube_search", "youtube_control"]:
    return self._handle_youtube(intent, text)
```

### With Intent Classifier
```json
// In label_map.json
"youtube_play": 17,
"youtube_search": 18,
"youtube_control": 19
```

## 💡 Pro Tips

1. **Lazy Loading**: Controller only initializes when needed
2. **Settings Persistence**: Changes automatically saved
3. **Auto Retry**: Handles transient failures gracefully
4. **Fallback Browsers**: Works with multiple browsers
5. **URL Support**: Can play direct YouTube URLs
6. **Hinglish**: Understands Hindi-English mix

## 🔐 Best Practices

✅ **DO**
- Use intent-based routing (youtube_play, youtube_search, youtube_control)
- Handle errors gracefully
- Validate user queries
- Use settings for user preferences
- Enable debug mode when troubleshooting

❌ **DON'T**
- Call yt_controller directly from action_router (use handle method)
- Hardcode settings (use YouTubeAutomationSettings)
- Ignore exceptions
- Run multiple instances simultaneously
- Modify config file manually (use settings API)

## 📞 Common Use Cases

### Use Case 1: Play Specific Video
```python
response = router.handle("youtube_play", "play shape of you")
# Response: "Playing shape of you on YouTube."
```

### Use Case 2: Search Videos
```python
response = router.handle("youtube_search", "search machine learning tutorials")
# Response: "Searching for machine learning tutorials on YouTube."
```

### Use Case 3: Control Playback
```python
response = router.handle("youtube_control", "mute")
# Response: "Muted."

response = router.handle("youtube_control", "set volume to 75")
# Response: "Volume set to 75%."
```

### Use Case 4: Adjust Settings
```python
settings = YouTubeAutomationSettings()
settings.browser = "chrome"  # Change browser
settings.default_speed = 1.5  # 1.5x speed
settings.max_retries = 3     # More retries
```

## 🚨 Troubleshooting

### YouTube not responding
1. Check if browser is installed
2. Verify internet connection
3. Try different browser: `settings.browser = "edge"`

### Query not being recognized
1. Ensure query is at least 1 character
2. Check for typos
3. Verify intent is correct

### Settings not persisting
1. Check write permissions on `BACKEND/DATA/config/`
2. Verify JSON file integrity
3. Reload settings: `settings.load_from_file()`

### Tests failing
1. Reset singleton: `YouTubeAutomationSettings._instance = None`
2. Check browser availability
3. Verify all dependencies installed

---

**Quick Links**
- [Full Documentation](README.md)
- [Technical Details](ENHANCEMENT_SUMMARY.md)
- [Test Files](test_youtube_*.py)
- [Configuration Module](youtube_automation_config.py)
