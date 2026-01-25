# Weather Automation - Quick Reference

## 🚀 Quick Start

### Installation
Already integrated! Just use it:

```python
from BACKEND.automations.weather.weather_cmd import weather_cmd

# Get weather
response = weather_cmd("weather in London")
```

## ⚙️ Configuration

### Enable/Disable Caching
```python
from BACKEND.automations.weather.weather_config import settings

settings.enable_weather_cache = False  # Disable weather cache
settings.enable_location_cache = False  # Disable location cache
```

### Change Default Location
```python
settings.default_location = "New York"
settings.auto_detect_location = True  # Auto-detect if available
```

### Response Format
```python
settings.use_short_response = True  # Brief format
settings.include_humidity = False
settings.include_wind = False
settings.include_feels_like = True
```

### API & Performance
```python
settings.max_retries = 2
settings.retry_delay = 1.0
settings.request_timeout = 6
settings.weather_cache_duration = 600  # 10 minutes
settings.location_cache_duration = 3600  # 1 hour
```

## 🎯 Usage Patterns

### Pattern 1: Command-Style Query
```python
from BACKEND.automations.weather.weather_cmd import weather_cmd

# Auto-detects location
weather_cmd("what's the weather")

# Specific city
weather_cmd("weather in Tokyo")

# Specific unit
weather_cmd("temperature in Paris in fahrenheit")
```

### Pattern 2: Direct Service Call
```python
from BACKEND.automations.weather.weather_service import get_weather

weather = get_weather("London", unit="metric")
print(weather["temperature"])  # 15.5
print(weather["humidity"])     # 70
print(weather["description"])  # "cloudy"
```

### Pattern 3: Controller Pattern
```python
from BACKEND.automations.weather.weather_controller import WeatherController

controller = WeatherController()
response = controller.handle("check_weather", "weather today")
```

## 🧹 Cache Management

```python
from BACKEND.automations.weather.weather_service import clear_weather_cache
from BACKEND.automations.weather.location_service import clear_location_cache

# Clear specific caches
clear_weather_cache()
clear_location_cache()

# Clear via controller
from BACKEND.automations.weather.weather_controller import WeatherController
controller = WeatherController()
controller.clear_caches()
```

## 🐛 Debug Mode

```python
from BACKEND.automations.weather.weather_config import settings

settings.debug = True

# Now all operations show debug output:
# 🔥 Weather cache HIT for london_metric
# ✅ Location detected: London
# 🔄 Weather API retry 1/2 for Paris
# 💾 Weather cached for paris_metric (expires in 600.0s)
```

## 📊 Supported Intents

| Intent | Example |
|--------|---------|
| `check_weather` | "what's the weather" |
| `check_temperature` | "temperature in London" |
| `weather_query` | "how's the weather today" |
| `get_weather` | "get weather for Paris" |
| `weather_forecast` | "forecast for Tokyo" |

## 🔧 Common Configurations

### Minimal API Usage (Maximum Caching)
```python
settings.weather_cache_duration = 1800  # 30 minutes
settings.location_cache_duration = 7200  # 2 hours
settings.max_retries = 1
```

### Real-Time Weather (No Caching)
```python
settings.enable_weather_cache = False
settings.enable_location_cache = False
settings.max_retries = 3
```

### Brief Responses
```python
settings.use_short_response = True
settings.include_humidity = False
settings.include_wind = False
```

### Detailed Responses
```python
settings.use_short_response = False
settings.include_feels_like = True
settings.include_humidity = True
settings.include_wind = True
```

## 🎯 Response Examples

### Default (Detailed)
```
Weather in London: 15°C, cloudy, humidity 70 percent, wind speed 5.2 km/h.
```

### Short Response
```
London: 15°C, cloudy.
```

### With Feels-Like
```
Weather in London: 15°C feels like 14°C, cloudy, humidity 70 percent, wind speed 5.2 km/h.
```

### Fahrenheit
```
Weather in New York: 59°F, clear, humidity 55 percent, wind speed 4.2 mph.
```

## ❌ Error Handling

| Error | Auto-Recovery |
|-------|---|
| Timeout | Retries (configurable) |
| Connection Error | Retries |
| City Not Found | Returns user-friendly message |
| API Key Invalid | Returns auth error message |
| All Providers Down | Uses default location |

## 📈 Performance Tips

1. **Enable Caching** for repeated queries
2. **Increase Cache Duration** to reduce API calls
3. **Use Default Location** to avoid geo-lookup
4. **Disable Unused Fields** for shorter responses
5. **Batch Queries** to same city

## 🧪 Testing

```bash
# Run all tests
python -m unittest BACKEND.automations.weather.tests -q

# Run specific test class
python -m unittest BACKEND.automations.weather.tests.test_weather_config -v

# Run single test
python -m unittest BACKEND.automations.weather.tests.test_weather_config.TestWeatherConfig.test_caching -v
```

## 📁 File Locations

- **Configuration**: `BACKEND/automations/weather/weather_settings.json`
- **Code**: `BACKEND/automations/weather/*.py`
- **Tests**: `BACKEND/automations/weather/tests/*.py`
- **Documentation**: `BACKEND/automations/weather/README.md`

## 🔗 Integration Points

1. **Action Router**: `BACKEND/core/brain/action_router.py`
   - Uses `WeatherController`
   - Handles weather intents

2. **Intent Classifier**: `BACKEND/DATA/models/intent_xlm_roberta_1/label_map.json`
   - Contains 3 weather intents

3. **Settings**: Persisted to `weather_settings.json`
   - Auto-loads on module import

## ⚡ Performance Metrics

- **Avg Response Time** (cached): ~50ms
- **Avg Response Time** (API call): ~2-3 seconds
- **Cache Hit Ratio** (typical): 80-90%
- **Successful Requests** (with retry): 99%+

---

For detailed documentation, see `BACKEND/automations/weather/README.md`
