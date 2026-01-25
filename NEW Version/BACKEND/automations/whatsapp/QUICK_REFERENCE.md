# WhatsApp Automation - Quick Reference

## Instant Usage

```python
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController

# Send a message
controller = WhatsAppController()
controller.send_message("John Doe", "Hello!")

# Or use NLP parsing
controller.handle("send message to Alice, Meeting at 3pm")
```

## Configuration (One-Time Setup)

```python
from BACKEND.automations.whatsapp.whatsapp_automation_config import get_settings

settings = get_settings()
settings.browser = "edge"  # or "chrome", "brave"
settings.preferred_backend = "auto"  # or "desktop", "web"
settings.debug_mode = True
```

## Message Formats

| Format | Example |
|--------|---------|
| Standard | "send to John, hello there" |
| Compact | "message Alice: meeting at 3pm" |
| Tell | "tell Bob that I'm ready" |
| Hinglish | "Rahul ko message bhej kaam done" |

## Settings Quick Access

```python
settings = get_settings()

# Backend
settings.preferred_backend = "auto"  # "auto", "desktop", "web"
settings.fallback_enabled = True

# Browser
settings.browser = "edge"  # "edge", "chrome", "brave"
settings.browser_profile = "Default"

# Retries
settings.max_retries = 2
settings.retry_delay = 3

# Timeouts
settings.desktop_ready_timeout = 40  # seconds
settings.web_load_delay = 15  # seconds

# Debug
settings.debug_mode = True
settings.verbose_logging = True
```

## Common Tasks

### Force Desktop

```python
settings.preferred_backend = "desktop"
```

### Force Web with Chrome

```python
settings.preferred_backend = "web"
settings.browser = "chrome"
```

### Increase Timeout for Slow Systems

```python
settings.desktop_ready_timeout = 60
settings.web_load_delay = 30
```

### Enable Debug Logging

```python
settings.debug_mode = True
settings.verbose_logging = True
```

## Error Handling

```python
from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppControllerError

try:
    controller.send_message("John", "Hello")
except WhatsAppControllerError as e:
    print(f"Failed: {e}")
```

## Testing

```bash
# Run all tests
python -m unittest discover BACKEND/automations/whatsapp/tests -v

# Run specific tests
python -m unittest BACKEND.automations.whatsapp.tests.test_config
python -m unittest BACKEND.automations.whatsapp.tests.test_message_parser
```

## Troubleshooting

### Desktop Not Working?

```python
# Force Web
settings.preferred_backend = "web"
```

### Wrong Browser?

```python
# Change browser
settings.browser = "chrome"  # or "brave"
```

### Timeout Too Short?

```python
# Increase timeouts
settings.desktop_ready_timeout = 60
settings.web_load_delay = 30
```

### Can't Parse Message?

```python
# Test parser
from BACKEND.automations.whatsapp.message_parser import parse_whatsapp_message
contact, msg = parse_whatsapp_message("send to John, hello")
print(f"Contact: {contact}, Message: {msg}")
```

## File Locations

- **Settings**: `BACKEND/DATA/config/whatsapp_settings.json`
- **Tests**: `BACKEND/automations/whatsapp/tests/`
- **Documentation**: `BACKEND/automations/whatsapp/README.md`

## Quick Validation

```python
# Validate contact
from BACKEND.automations.whatsapp.message_parser import validate_contact, validate_message

valid = validate_contact("John Doe")  # True
valid = validate_message("Hello there")  # True
```

## Backend Info

```python
# Check current backend
info = controller.get_backend_info()
print(info)  # {'backend': 'desktop', 'backend_class': 'WhatsAppDesktop', ...}
```

## Settings Persistence

Settings automatically save to JSON file:
- Location: `BACKEND/DATA/config/whatsapp_settings.json`
- Auto-loaded on next initialization
- Manual reset: `settings.reset_to_defaults()`

## Supported Patterns

✅ Send to X, Y
✅ Send to X that Y
✅ Message X: Y
✅ Ping X saying Y
✅ Tell X that Y
✅ X ko message bhej Y (Hinglish)
✅ Unicode/Emoji support
