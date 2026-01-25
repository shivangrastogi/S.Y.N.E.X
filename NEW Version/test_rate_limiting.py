#!/usr/bin/env python3
"""
Test script for rate limiting security
"""
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from BACKEND.core.security.rate_limiter import RateLimiter

# Test the rate limiter
limiter = RateLimiter()

print("╔════════════════════════════════════════╗")
print("║     RATE LIMITER TEST SUITE            ║")
print("╚════════════════════════════════════════╝\n")

# Test 1: Input rate limiting
print("TEST 1: Input Rate Limiting (300ms minimum)")
print("-" * 50)
for i in range(5):
    ok, reason = limiter.check_input_rate()
    print(f"  Attempt {i+1}: {'✅ OK' if ok else f'❌ BLOCKED: {reason}'}")
    time.sleep(0.2)  # 200ms - should block on 2nd attempt

print()

# Test 2: Duplicate command detection
print("TEST 2: Duplicate Command Detection (3s timeout)")
print("-" * 50)
limiter.reset()
commands = ["hello", "hello", "goodbye", "hello", "goodbye", "goodbye"]
for cmd in commands:
    ok, reason = limiter.check_duplicate(cmd)
    print(f"  '{cmd}': {'✅ OK' if ok else f'❌ BLOCKED: {reason}'}")
    time.sleep(0.1)

print()

# Test 3: Gesture toggle rate limiting
print("TEST 3: Gesture Mode Toggle Rate Limiting (1s minimum)")
print("-" * 50)
limiter.reset()
for i in range(5):
    ok, reason = limiter.check_gesture_toggle_rate()
    print(f"  Toggle {i+1}: {'✅ OK' if ok else f'❌ BLOCKED: {reason}'}")
    time.sleep(0.4)  # 400ms - should block on 2nd attempt

print()

# Test 4: TTS rate limiting
print("TEST 4: TTS Rate Limiting (100ms minimum)")
print("-" * 50)
limiter.reset()
for i in range(5):
    ok = limiter.check_tts_rate()
    print(f"  TTS {i+1}: {'✅ OK' if ok else '❌ BLOCKED'}")
    time.sleep(0.05)  # 50ms - should block frequently

print()
print("╔════════════════════════════════════════╗")
print("║     ALL TESTS COMPLETED                ║")
print("╚════════════════════════════════════════╝")
