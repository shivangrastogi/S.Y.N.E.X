
import json
import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class NotificationManager:
    """
    Unified Notification Manager for JARVIS.
    Supports file persistence (common file) and real-time callbacks.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(NotificationManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, storage_file: str = "data/notifications.json"):
        if getattr(self, 'initialized', False):
            return
        self.storage_file = storage_file
        self.notifications = []
        self.callbacks = []
        self._ensure_storage_exists()
        self.load_from_file()
        self.initialized = True

    def _ensure_storage_exists(self):
        Path(self.storage_file).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_from_file(self):
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.notifications = json.load(f)
        except Exception as e:
            logger.error(f"Error loading notifications: {e}")
            self.notifications = []

    def _save_to_file(self):
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.notifications, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving notifications: {e}")

    def add(self, notification: Dict) -> bool:
        """New Hub-style add method. Wraps legacy add_notification."""
        app = notification.get("app") or notification.get("app_name") or "Unknown"
        title = notification.get("title", "")
        text = notification.get("text", "")
        notif_id = notification.get("key") or notification.get("id") or str(len(self.notifications))
        
        return self.add_notification(app, title, text, notif_id)

    def add_notification(self, app_name: str, title: str, text: str, notif_id: str):
        """Standard notification addition with persistence and callbacks"""
        # Check if exists (update)
        for i, n in enumerate(self.notifications):
            if n.get('id') == notif_id or n.get('key') == notif_id:
                self.notifications[i] = {
                    'app': app_name,
                    'app_name': app_name,
                    'title': title,
                    'text': text,
                    'id': notif_id,
                    'key': notif_id
                }
                self._save_to_file()
                self._notify_listeners('update', self.notifications[i])
                return True

        # New
        notif = {
            'app': app_name,
            'app_name': app_name,
            'title': title,
            'text': text,
            'id': notif_id,
            'key': notif_id
        }
        self.notifications.insert(0, notif) # Most recent first
        self._save_to_file()
        self._notify_listeners('add', notif)
        logger.info(f"Notification added: {app_name} - {title}")
        return True

    def delete(self, notif_id: str) -> bool:
        """Delete a notification by ID"""
        for i, n in enumerate(self.notifications):
            if n.get('id') == notif_id or n.get('key') == notif_id:
                removed = self.notifications.pop(i)
                self._save_to_file()
                self._notify_listeners('delete', removed)
                logger.info(f"Notification deleted: {notif_id}")
                return True
        return False

    def clear_all(self):
        """Clear all notifications"""
        self.notifications.clear()
        self._save_to_file()
        self._notify_listeners('clear', None)
        logger.info("All notifications cleared")
        return True

    def get_all(self) -> List[Dict]:
        return self.notifications

    def register_callback(self, callback):
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def _notify_listeners(self, action, data):
        for cb in self.callbacks:
            try:
                cb(action, data)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")
