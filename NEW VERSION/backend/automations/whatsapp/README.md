# WhatsApp Automation Module

## Overview

The WhatsApp Automation Module provides professional-grade automation for sending messages via WhatsApp Desktop or WhatsApp Web. It features intelligent backend detection, comprehensive error handling, retry logic, and extensive configuration options.

## Features

### Core Capabilities
- **Dual Backend Support**: WhatsApp Desktop and WhatsApp Web
- **Intelligent Auto-Detection**: Automatically selects best available backend
- **Smart Fallback**: Desktop → Web automatic fallback
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Multi-Browser Support**: Edge, Chrome, Brave
- **Natural Language Parsing**: Multiple message formats and Hinglish support
- **Unicode Support**: Hindi, Emoji, and international characters via pyperclip
- **Comprehensive Error Handling**: Custom exceptions and detailed error messages

### Advanced Features
- **Singleton Settings**: Centralized JSON-persisted configuration
- **Contact Validation**: Name format and length validation
- **Message Validation**: Length limits and content validation
- **Debug Mode**: Verbose logging for troubleshooting
- **Browser Tab Reuse**: Efficient tab management
- **Window Management**: Auto-focus and window control

## Architecture

```
whatsapp/
├── whatsapp_automation_config.py  # Settings singleton with JSON persistence
├── whatsapp_controller.py          # Main controller with intelligent routing
├── whatsapp_desktop.py             # Desktop backend with retry logic
├── whatsapp_web.py                 # Web backend with retry logic
├── message_parser.py               # Enhanced NLP parser with validation
├── browser_manager.py              # Browser launcher with fallback
├── window_utils.py                 # Window management utilities
├── whatsapp_state.py               # Global state management
├── whatsapp_config.py              # Legacy config (deprecated)
└── tests/
    ├── test_config.py              # Settings tests (20+ tests)
    └── test_message_parser.py      # Parser tests (35+ tests)
```

## Quick Start

### Basic Usage

```python
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController

# Initialize controller (auto-detects backend)
controller = WhatsAppController()

# Send a message
controller.send_message("John Doe", "Hello from JARVIS!")

# Use intent routing (with NLP parsing)
response = controller.handle("send message to Alice, Meeting at 3pm")
print(response)  # "✅ Message sent to Alice: Meeting at 3pm..."
```

### Configuration

```python
from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings

# Get settings instance
settings = get_settings()

# Configure backend preference
settings.preferred_backend = "desktop"  # "auto" | "desktop" | "web"
settings.fallback_enabled = True

# Configure browser (for Web)
settings.browser = "edge"  # "edge" | "chrome" | "brave"
settings.browser_profile = "Default"

# Configure retry logic
settings.max_retries = 3
settings.retry_delay = 5  # seconds
settings.retry_backoff_multiplier = 2.0

# Configure timeouts
settings.desktop_launch_timeout = 10  # seconds
settings.web_load_delay = 15  # seconds

# Enable debugging
settings.debug_mode = True
settings.verbose_logging = True

# Settings auto-save to DATA/config/whatsapp_settings.json
```

## Message Format Support

### Supported Formats

```python
# Standard formats
"send message to John, hello there"
"send to Sarah, meeting at 3pm"
"send to Bob that I'll be late"

# Compact formats
"message Alice: can you call me?"
"ping David saying are you free?"
"text Mike, how are you?"

# Tell format
"tell Sarah that meeting is canceled"

# Hinglish format
"Rahul ko message bhej khana ready hai"

# Direct format
"send John hello there"
```

### Parser Behavior

- **Case Insensitive**: "SEND TO JOHN" works
- **Noise Removal**: "whatsapp", "message", "a" are removed
- **Contact Capitalization**: "john doe" → "John Doe"
- **Message Cleaning**: Removes "that", ":", "-" prefixes
- **Whitespace Normalization**: Multiple spaces handled
- **Validation**: Contact and message length/format checks

## Backend Selection Logic

### Auto-Detection (Default)

```python
settings.preferred_backend = "auto"
```

1. Check if WhatsApp Desktop is installed (Registry + paths)
2. Test if Desktop can launch (3 methods)
3. If Desktop available → Use Desktop
4. Otherwise → Use Web

### Force Desktop

```python
settings.preferred_backend = "desktop"
```

- Uses Desktop if available
- Falls back to Web if `fallback_enabled=True`
- Raises error if Desktop unavailable and fallback disabled

### Force Web

```python
settings.preferred_backend = "web"
```

- Always uses WhatsApp Web
- Ignores Desktop even if installed

## Retry Logic

### Desktop Retry

```python
# Configuration
settings.max_retries = 2  # Total attempts = 3 (1 initial + 2 retries)
settings.retry_delay = 3  # Base delay
settings.retry_backoff_multiplier = 2.0  # Exponential backoff

# Behavior
# Attempt 1: Immediate
# Attempt 2: Wait 3s (retry_delay * 2^0)
# Attempt 3: Wait 6s (retry_delay * 2^1)
```

### Web Retry

- Same retry logic as Desktop
- Independent retry counts
- Falls back to Desktop if Desktop→Web fallback enabled

### Browser Launch Retry

```python
# Browser manager retries:
# 1. Try preferred browser
# 2. Try fallback browsers (Edge → Chrome → Brave)
# 3. Retry each browser with configured delay
```

## Error Handling

### Custom Exceptions

```python
from BACKEND.automations.whatsapp.whatsapp_desktop import WhatsAppDesktopError
from BACKEND.automations.whatsapp.whatsapp_web import WhatsAppWebError
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppControllerError
from BACKEND.automations.whatsapp.message_parser import MessageParserError
from BACKEND.automations.whatsapp.browser_manager import BrowserManagerError

try:
    controller.send_message("John", "Hello")
except WhatsAppDesktopError as e:
    print(f"Desktop failed: {e}")
except WhatsAppWebError as e:
    print(f"Web failed: {e}")
except WhatsAppControllerError as e:
    print(f"Controller error: {e}")
```

### Error Categories

1. **Parsing Errors** (`MessageParserError`)
   - Invalid message format
   - Contact validation failure
   - Message length exceeded

2. **Desktop Errors** (`WhatsAppDesktopError`)
   - Launch failure (all methods exhausted)
   - Timeout (app not ready)
   - Process not found

3. **Web Errors** (`WhatsAppWebError`)
   - Browser launch failure
   - Page load timeout
   - QR scan timeout

4. **Controller Errors** (`WhatsAppControllerError`)
   - Both backends failed
   - Fallback disabled and primary failed

## Settings Reference

### Backend Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `preferred_backend` | str | "auto" | "auto", "desktop", "web" |
| `fallback_enabled` | bool | True | Enable Desktop→Web fallback |
| `auto_detect_desktop` | bool | True | Auto-detect Desktop installation |

### Browser Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `browser` | str | "edge" | "edge", "chrome", "brave" |
| `browser_profile` | str | "Default" | Browser profile name |
| `browser_user_data_dir` | str | "" | Custom user data directory |

### Timeout Configuration

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `desktop_launch_timeout` | int | 10 | 1-60 | Desktop launch timeout (seconds) |
| `desktop_ready_timeout` | int | 40 | 5-120 | Desktop ready timeout (seconds) |
| `web_load_delay` | int | 15 | 5-60 | Web page load delay (seconds) |
| `web_ready_timeout` | int | 30 | 5-120 | Web ready timeout (seconds) |
| `web_qr_scan_timeout` | int | 120 | 30-300 | Web QR scan timeout (seconds) |

### Message Configuration

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `typing_interval` | float | 0.05 | 0.01-1.0 | Seconds between keystrokes |
| `send_delay` | float | 0.5 | - | Delay before sending (seconds) |
| `message_max_length` | int | 5000 | 1-10000 | Max message characters |
| `allow_empty_messages` | bool | False | - | Allow empty messages |

### Retry Configuration

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `retry_enabled` | bool | True | - | Enable retry logic |
| `max_retries` | int | 2 | 0-5 | Maximum retry attempts |
| `retry_delay` | int | 3 | 1-30 | Base retry delay (seconds) |
| `retry_backoff_multiplier` | float | 2.0 | 1.0-5.0 | Exponential backoff multiplier |

### Debug Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `debug_mode` | bool | False | Enable debug output |
| `verbose_logging` | bool | False | Enable verbose logging |
| `screenshot_on_error` | bool | False | Screenshot on failure |

## Testing

### Run All Tests

```bash
# Run all WhatsApp tests
python -m unittest discover BACKEND/automations/whatsapp/tests -v

# Run specific test modules
python -m unittest BACKEND.automations.whatsapp.tests.test_config -v
python -m unittest BACKEND.automations.whatsapp.tests.test_message_parser -v
```

### Test Coverage

- **Settings Tests**: 20+ tests covering:
  - Singleton pattern
  - Validation (backend, browser, timeouts, retries)
  - Persistence (JSON save/load)
  - Default values
  - Bulk updates

- **Parser Tests**: 35+ tests covering:
  - 10+ message formats
  - Contact validation (length, characters)
  - Message validation (length, unicode)
  - Cleaning and normalization
  - Hinglish support
  - Error handling

## Integration with JARVIS

### Action Router Integration

```python
# In action_router.py
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController

class ActionRouter:
    def __init__(self, speaker):
        self.whatsapp = WhatsAppController()
        
    def route_action(self, label, text):
        if label == "send_whatsapp":
            return self.whatsapp.handle(text)
```

### Intent Mapping

```json
{
  "send_whatsapp_message": 17,
  "whatsapp_send": 18,
  "message_whatsapp": 19
}
```

## Future Enhancements

### Planned Features

1. **Message Queue**
   - Batch sending
   - Rate limiting
   - Priority queue

2. **Scheduling**
   - Delayed messages
   - Recurring messages
   - Timezone support

3. **Attachments**
   - Image sending
   - Document sharing
   - Voice notes

4. **Advanced Features**
   - Group messaging
   - Broadcast lists
   - Contact search
   - Message history

5. **Performance**
   - Parallel message sending
   - Contact cache
   - Session persistence

6. **Analytics**
   - Send statistics
   - Failure tracking
   - Performance metrics

## Troubleshooting

### Desktop Not Launching

```python
# Enable debug mode
settings = get_settings()
settings.debug_mode = True
settings.verbose_logging = True

# Check Desktop installation
from BACKEND.automations.whatsapp.whatsapp_controller import is_whatsapp_desktop_installed
print(f"Desktop installed: {is_whatsapp_desktop_installed()}")

# Force Web as fallback
settings.preferred_backend = "web"
```

### Browser Not Found

```python
# Check browser installation
import os

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

print(f"Edge: {os.path.exists(edge_path)}")
print(f"Chrome: {os.path.exists(chrome_path)}")

# Try alternative browser
settings.browser = "chrome"
```

### Message Parsing Failure

```python
# Test parser directly
from BACKEND.automations.whatsapp.message_parser import parse_whatsapp_message

contact, message = parse_whatsapp_message("your text here")
print(f"Contact: {contact}, Message: {message}")

# Use different format
"send to John, hello"  # Try comma separator
"message John: hello"  # Try colon separator
```

### Timeout Issues

```python
# Increase timeouts
settings.desktop_ready_timeout = 60  # Increase to 60s
settings.web_load_delay = 30  # Increase to 30s
```

## Dependencies

### Required Packages

```
pyautogui>=0.9.53
pygetwindow>=0.0.9
psutil>=5.9.0
pyperclip>=1.8.2  # For unicode support
```

### Optional Packages

```
PIL>=9.0.0  # For screenshots
```

## License

Part of the JARVIS automation ecosystem.

## Support

For issues and feature requests, contact the JARVIS development team.
