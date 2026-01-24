# CORE/Utils/Logger.py
import logging
import os

# --- Create a 'logs' directory if it doesn't exist ---
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# --- Private function to set up a logger ---
def _setup_logger(logger_name, log_file, level=logging.INFO):
    """Helper function to create a logger."""
    try:
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', "%Y-%m-%d %H:%M:%S"))

        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        if not logger.hasHandlers():  # Avoid duplicate logs
            logger.addHandler(handler)

        return logger
    except Exception as e:
        print(f"CRITICAL: Failed to set up logger '{logger_name}'. Error: {e}")
        return None


# --- Logger 1: For System Errors (API failures, crashes, etc.) ---
error_log_path = os.path.join(LOG_DIR, "jarvis_errors.log")
error_logger = _setup_logger('error_logger', error_log_path, level=logging.ERROR)

# --- Logger 2: For Re-training Data (NLU failures) ---
retrain_log_path = os.path.join(LOG_DIR, "jarvis_retrain.log")
retrain_logger = _setup_logger('retrain_logger', retrain_log_path)


# --- Public Functions ---
def log_error(message):
    """Logs a system-level error to jarvis_errors.log"""
    if error_logger:
        error_logger.error(message)
    else:
        print(f"LOG_ERROR (logger not init'd): {message}")


def log_retrain(message):
    """Logs an NLU failure to jarvis_retrain.log for later training."""
    if retrain_logger:
        retrain_logger.info(message)
    else:
        print(f"LOG_RETRAIN (logger not init'd): {message}")