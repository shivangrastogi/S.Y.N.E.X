# BACKEND/automations/weather/test_weather.py

from BACKEND.automations.weather.weather_cmd import weather_cmd


def test_weather_queries():
    """Test various weather queries"""
    test_cases = [
        # (query, description)
        ("what's the weather today", "General weather query"),
        ("weather in london", "Specific city - London"),
        ("temperature in new york", "Temperature query"),
        ("how hot is it in tokyo", "Hot weather query"),
        ("weather in paris in fahrenheit", "Fahrenheit request"),
        ("what's the temperature in mumbai", "Temperature specific"),
        ("forecast for berlin", "Forecast query"),
        ("climate in sydney", "Climate query"),
        ("how's the weather", "General with no location"),
        ("is it cold outside", "Temperature feel query"),
    ]

    print("🧪 Weather Module Test Suite")
    print("=" * 50)

    for query, description in test_cases:
        print(f"\n{'=' * 50}")
        print(f"Test: {description}")
        print(f"Query: '{query}'")
        print(f"{'=' * 50}")

        try:
            response = weather_cmd(query, speak=True)
            if response:
                print(f"✅ Response: {response}")
            else:
                print("❌ No response")
        except Exception as e:
            print(f"❌ Error: {e}")


def test_weather_service_direct():
    """Test weather service directly"""
    print("\n\n🧪 Direct Weather Service Test")
    print("=" * 50)

    from BACKEND.automations.weather.weather_service import get_weather

    test_cities = ["London", "New York", "Tokyo", "Mumbai", "Sydney"]

    for city in test_cities:
        try:
            print(f"\nTesting: {city}")
            weather = get_weather(city)
            print(f"✅ Success: {weather['temperature']}°C, {weather['description']}")
        except Exception as e:
            print(f"❌ Failed: {e}")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("🌤 WEATHER MODULE TESTING")
    print("=" * 60)

    # Test 1: Query parsing and weather fetching
    test_weather_queries()

    # Test 2: Direct service test
    test_weather_service_direct()

    print("\n" + "=" * 60)
    print("✅ Weather testing complete")
    print("=" * 60)


if __name__ == "__main__":
    main()