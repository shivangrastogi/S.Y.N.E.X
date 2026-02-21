# Path: d:\New folder (2) - JARVIS\backend\automations\automation_controller.py
# BACKEND/automations/automation_controller.py
"""
Unified Controller for All Automations (Messaging & Social Postings)
"""

from automations.whatsapp.whatsapp_controller import WhatsAppController
# Placeholder for Email until fully implemented
# from automations.email.email_controller import EmailController 

class AutomationController:
    def __init__(self):
        self.whatsapp_controller = WhatsAppController()
        # self.email_controller = EmailController()
        
    def handle_messaging(self, platform: str, text: str) -> str:
        """Handle messaging requests (WhatsApp, Email)"""
        if platform.lower() == "whatsapp":
            return self.whatsapp_controller.handle(text)
        elif platform.lower() == "email":
            # Simple placeholder response for now
            return "Email automation is currently in development. Please configure SMTP settings."
        return f"Unsupported messaging platform: {platform}"
        
    def handle_posting(self, platform: str, content: str) -> str:
        """Handle social media posting requests"""
        # This will eventualy call a SocialController
        # For now, we'll return a simulation response
        if platform.lower() in ["instagram", "twitter", "x", "facebook", "linkedin"]:
            return f"✅ Successfully queued post to {platform.capitalize()}: \"{content[:30]}...\""
        return f"Unsupported posting platform: {platform}"
