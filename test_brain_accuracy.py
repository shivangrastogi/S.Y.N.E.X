import os
import sys
import logging
import time

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.intent_classifier import IntentClassifier

# Disable logging to keep output clean
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("core.intent_classifier").setLevel(logging.WARNING)

def run_accuracy_test():
    _ROOT = os.path.dirname(os.path.abspath(__file__))
    intents_path = os.path.join(_ROOT, "data", "intents.json")
    models_dir = os.path.join(_ROOT, "data", "models")

    print("\n" + "="*50)
    print(" JARVIS BRAIN ACCURACY STRESS TEST")
    print("="*50)

    print("\n[1/3] Loading Brain...")
    clf = IntentClassifier(intents_path, models_dir)
    
    # Test Cases: (Input Sentence -> Expected Intent)
    # We use variations NOT in the intents.json to test true generalization
    test_suite = [
        ("chrome open karo", "open_app"),
        ("mujhe notepad chahiye", "open_app"),
        ("music band kar do", "stop_music"),
        ("aaj ka mausam kaisa hai", "get_weather"),
        ("calculator chalao", "open_app"),
        ("ek screenshot le lo", "take_screenshot"),
        ("volume thoda kam karo", "volume_down"),
        ("google pe search karo python tutorial", "search_web"),
        ("computer lock kar do", "lock_screen"),
        ("youtube pe arijit singh ke gaane chalao", "play_youtube"),
        ("shukriya jarvis", "greet"),
        ("hello kaise ho", "greet"),
        ("bhai time kya ho raha hai", "get_time"),
    ]

    print(f"[2/3] Running {len(test_suite)} stress tests...")
    print("-" * 60)
    print(f"{'Input Sentence':<40} | {'Status':<10}")
    print("-" * 60)

    passed = 0
    start_time = time.time()

    for query, expected in test_suite:
        pred = clf.predict(query)
        is_correct = (pred.intent == expected)
        
        status = "✅ PASS" if is_correct else "❌ FAIL"
        if is_correct:
            passed += 1
        
        print(f"{query:<40} | {status}")
        if not is_correct:
            print(f"    └─ Expected: {expected}, Got: {pred.intent} (Conf: {pred.confidence:.2f})")

    total_time = time.time() - start_time
    accuracy = (passed / len(test_suite)) * 100

    print("-" * 60)
    print(f"[3/3] TEST COMPLETE")
    print(f"      Total Tests: {len(test_suite)}")
    print(f"      Passed     : {passed}")
    print(f"      Failed     : {len(test_suite) - passed}")
    print(f"      Accuracy   : {accuracy:.1f}%")
    print(f"      Avg Speed  : {(total_time/len(test_suite))*1000:.1f}ms per query")
    print("="*50)

    if accuracy > 80:
        print("\nRESULT: Your Brain is ready for the interview! 🚀")
    else:
        print("\nRESULT: Brain needs more examples in intents.json. 🧠")

if __name__ == "__main__":
    run_accuracy_test()
