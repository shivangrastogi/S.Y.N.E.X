# Weather Automation Module

Professional, production-ready weather automation for JARVIS with caching, retry logic, and configurable behavior.

## Architecture

### Core Components

1. **weather_config.py** - `WeatherAutomationSettings` (Singleton)
   - JSON-persisted configuration
   - Caching control (weather, location)
   - Retry logic parameters
   - Location preferences
   - Response formatting options
   - Timezone/unit preferences

2. **weather_service.py** - `get_weather()`
   - API calls with retry logic
   - Response caching (default: 10 minutes)
   - Error handling for 404 (city not found), 401 (API key), timeouts
   - Configurable decimal precision
   - Cache key generation by city+unit

3. **location_service.py** - `get_current_location()`
   - Multi-provider IP geolocation fallback
   - Location caching (default: 1 hour)
   - Hostname detection fallback
   - Auto-detection toggle
   - Separate location cache from weather cache

4. **weather_parser.py** - `parse_weather_query()`
   - Extract city name from natural language queries
   - Unit detection (Celsius/Fahrenheit)
   - City name capitalization
   - Hinglish support (e.g., "Mumbai ka weather")
   - Invalid city filtering

5. **weather_cmd.py** - `weather_cmd()`
   - Unified command handler
   - Settings-driven response formatting
   - Optional fields: feels_like, humidity, wind, pressure, visibility
   - Short vs. detailed response modes
   - User-friendly error messages

6. **weather_controller.py** - `WeatherController`
   - Intent routing interface
   - Cache management
   - Settings access and updates
   - Matches battery/google/network controller patterns

## Configuration

Settings are stored in `BACKEND/automations/weather/weather_settings.json`:

```json
{
  "enable_weather_cache": true,
  "weather_cache_duration": 600,  // 10 minutes
  "enable_location_cache": true,
  "location_cache_duration": 3600, // 1 hour
  "max_retries": 2,
  "retry_delay": 1.0,
  "request_timeout": 6,
  "default_location": "London",
  "auto_detect_location": true,
  "default_unit": "metric",  // or "imperial"
  "include_feels_like": true,
  "include_humidity": true,
  "include_wind": true,
  "use_short_response": false,
  "debug": false
}
```

### Customizing Settings

```python
from BACKEND.automations.weather.weather_config import settings

# Toggle caching
settings.enable_weather_cache = False

# Change cache duration (seconds)
settings.weather_cache_duration = 300  # 5 minutes

# Change default location
settings.default_location = "New York"

# Set response format
settings.use_short_response = True

# Enable debug
settings.debug = True

# Reset to defaults
settings.reset_to_defaults()
```

## Usage Examples

### Basic Weather Query

```python
from BACKEND.automations.weather.weather_cmd import weather_cmd

# Auto-detects location and uses default unit
response = weather_cmd("what's the weather")
# Output: "Weather in London: 15°C, cloudy, humidity 70 percent, wind speed 5.2 km/h."

# Specific city
response = weather_cmd("weather in Tokyo")
# Output: "Weather in Tokyo: 22°C, sunny, humidity 60 percent, wind speed 3.5 km/h."

# Temperature in Fahrenheit
response = weather_cmd("temperature in New York in fahrenheit")
# Output: "Weather in New York: 59°F, clear, humidity 55 percent, wind speed 4.2 mph."
```

### Direct Service Calls

```python
from BACKEND.automations.weather.weather_service import get_weather, clear_weather_cache

# Get detailed weather data
weather = get_weather("London", unit="metric")
print(weather["temperature"])  # 15.5
print(weather["description"])   # "cloudy"
print(weather["humidity"])      # 70

# Clear cache
clear_weather_cache()
```

### Location Detection

```python
from BACKEND.automations.weather.location_service import (
    get_current_location,
    get_default_location,
    clear_location_cache
)

# Auto-detect
city = get_current_location()  # Returns detected city or None

# Get configured default
city = get_default_location()  # Returns "London" (or configured default)

# Clear cache
clear_location_cache()
```

### Controller Interface

```python
from BACKEND.automations.weather.weather_controller import WeatherController

controller = WeatherController()

# Handle intents
response = controller.handle("check_weather", "what's the weather today")

# Direct query
response = controller.get_weather("weather in Mumbai")

# Settings management
config = controller.get_settings()
controller.update_setting("default_unit", "imperial")

# Cache management
controller.clear_caches()
```

## Intent Integration

### Supported Intents

- `check_weather` - General weather query
- `check_temperature` - Temperature-specific query
- `weather_query` - Alias for weather queries
- `get_weather` - Alternative query format
- `weather_forecast` - Forecast request (uses same data)

All intents route through `action_router.py` via `WeatherController`.

### Intent Routing

In `BACKEND/core/brain/action_router.py`:

```python
# Weather automation is initialized
self.weather = WeatherController()

# In handle() method
weather_response = self.weather.handle(intent, text)
if weather_response:
    return weather_response
```

### Label Map

Updated `BACKEND/DATA/models/intent_xlm_roberta_1/label_map.json` includes:
- `check_weather` (14)
- `check_temperature` (15)
- `weather_query` (16)

## Caching Strategy

### Weather Caching (Default: 10 minutes)

- Key: `{city}_{unit}` (e.g., "london_metric")
- Invalidates after `weather_cache_duration` seconds
- Respects `enable_weather_cache` setting

### Location Caching (Default: 1 hour)

- Single cached location (not city-specific)
- Invalidates after `location_cache_duration` seconds
- Respects `enable_location_cache` setting

### Cache Clearing

```python
from BACKEND.automations.weather.weather_service import clear_weather_cache
from BACKEND.automations.weather.location_service import clear_location_cache

clear_weather_cache()
clear_location_cache()

# Or via controller
controller.clear_caches()
```

## Error Handling

### Weather Service Errors

| Error | Response |
|-------|----------|
| 404 City Not Found | "City '{city}' not found..." |
| 401 API Key Invalid | "Weather API authentication failed..." |
| Timeout | "Request timed out" → retry |
| Connection Error | "Network connection error" → retry |
| Unexpected Response | "Weather service returned unexpected..." |

### Location Service Errors

- Provider fails → tries next provider
- All providers fail → tries hostname detection
- All fail → returns configured default location

## Testing

### Test Suite

```
BACKEND/automations/weather/tests/
├── __init__.py
├── test_weather_config.py       (17 tests)
├── test_weather_modules.py      (25 tests)
```

### Running Tests

```bash
# Config tests only
python -m unittest BACKEND.automations.weather.tests.test_weather_config -v

# Service/parser/location tests
python -m unittest BACKEND.automations.weather.tests.test_weather_modules -v

# Specific test class
python -m unittest BACKEND.automations.weather.tests.test_weather_modules.TestWeatherService -v

# Specific test
python -m unittest BACKEND.automations.weather.tests.test_weather_config.TestWeatherConfig.test_caching -v
```

### Test Coverage

- **Config Tests**: Singleton, persistence, validation, defaults
- **Service Tests**: Caching, retry logic, error handling, city not found
- **Location Tests**: Detection, caching, fallback, auto-detect toggle
- **Parser Tests**: City extraction, unit detection, invalid filtering
- **Mocking**: requests.get, socket.gethostname, env_required

## Future Scope

### Planned Enhancements

1. **Multiple Weather Providers**
   - Add OpenWeatherMap alternatives
   - Support WeatherAPI, Weatherstack
   - Provider fallback logic

2. **Extended Forecast**
   - 5-day forecast
   - Hourly breakdown
   - Severe weather alerts

3. **Location History**
   - Favorite locations
   - Recent queries
   - Location-based preferences

4. **Advanced Formatting**
   - Weather emoji support
   - Multi-language responses
   - Personalized alerts (e.g., "wear jacket")

5. **Integration**
   - Calendar sync (events based on weather)
   - Outfit suggestions
   - Activity recommendations

6. **Performance**
   - Batch location caching
   - Compressed response data
   - CDN for API responses

## Debugging

### Enable Debug Mode

```python
from BACKEND.automations.weather.weather_config import settings

settings.debug = True
```

Debug output will show:
- Cache hits/misses with expiry times
- Provider attempts and failures
- Retry attempts
- Cached data operations

Example output:
```
🧹 Weather cache cleared
🌐 Trying location provider: http://ip-api.com/json
✅ Location detected: London
💾 Location cached: London (expires in 3600.0s)
🔥 Weather cache HIT for london_metric
🔄 Weather API retry 1/2 for Paris
```

## Dependencies

- `requests` - HTTP requests with timeouts
- `os` - File I/O for settings
- `json` - Settings persistence
- `datetime` - Cache expiry tracking
- `socket` - Hostname detection (fallback)

## Architecture Alignment

The weather module follows the same professional patterns as battery, Google, and network automations:

✅ Settings singleton with JSON persistence
✅ Caching with configurable TTL
✅ Retry logic with exponential backoff
✅ Error handling with user-friendly messages
✅ Controller for intent routing
✅ Comprehensive unit tests (25+ tests)
✅ Multi-provider fallback
✅ Debug mode for troubleshooting

---

**Version**: 1.0.0  
**Status**: Production Ready  
**Last Updated**: January 2026
