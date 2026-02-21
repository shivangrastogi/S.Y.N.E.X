# BACKEND/automations/whatsapp/whatsapp_config.py
import json
import os

CONFIG_PATH = "../../DATA/whatsapp_config.json"

DEFAULT_CONFIG = {
    "browser": "edge",          # edge | chrome
    "profile": "Default"        # Edge profile name
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
