# BACKEND/automations/youtube/yt_controller.py
from BACKEND.automations.youtube.yt_session import YouTubeSession
from BACKEND.automations.youtube.yt_player import YouTubePlayer
from BACKEND.automations.youtube.yt_search import (
    search_only,
    search_and_play_first
)
from BACKEND.automations.youtube.youtube_query_parser import (
    parse_youtube_query,
    parse_player_command
)
from BACKEND.automations.youtube.youtube_automation_config import YouTubeAutomationSettings
from BACKEND.automations.youtube.yt_exceptions import YouTubeQueryError
import time


class YouTubeController:
    """
    Enhanced YouTube Controller with intent-based routing
    Supports ML intents, query parsing, and player controls
    """
    
    def __init__(self):
        self.session = YouTubeSession()
        self.settings = YouTubeAutomationSettings()

    def _driver(self):
        return self.session.get_driver()

    def handle(self, intent: str, text: str):
        """
        Main entry point for intent-based YouTube automation
        
        Args:
            intent: The intent from ML classifier (youtube_play, youtube_search, youtube_control)
            text: The user's original query text
            
        Returns:
            str: Response message for the user
        """
        print(f"🎥 YouTube Controller handling intent: {intent}")
        
        try:
            # Parse query with retry
            max_retries = self.settings.retry.max_attempts
            
            for attempt in range(max_retries):
                try:
                    # Handle play/search intents
                    if intent in ["youtube_play", "youtube_search"]:
                        return self._handle_play_search(intent, text)
                    
                    # Handle player control intents
                    elif intent == "youtube_control":
                        return self._handle_player_control(text)
                    
                    else:
                        return f"Unknown YouTube intent: {intent}"
                
                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ YouTube attempt {attempt + 1} failed: {error_msg}")
                    
                    if attempt == max_retries - 1:
                        return f"Failed to execute YouTube command after {max_retries} attempts: {error_msg}"
                    
                    # Wait before retry with exponential backoff
                    wait_time = self.settings.retry.delay * (self.settings.retry.backoff_multiplier ** attempt)
                    print(f"🔄 Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        except Exception as e:
            return f"YouTube automation error: {str(e)}"

    def _handle_play_search(self, intent: str, text: str):
        """Handle play and search intents"""
        try:
            # Parse query
            parsed = parse_youtube_query(text)
            
            if not parsed.get('query'):
                return "What should I play on YouTube?"
            
            query = parsed['query']
            action = parsed.get('action', 'play')  # Default to play
            
            print(f"📺 Action: {action}, Query: {query}")
            
            # Execute based on action
            if action == 'play' or intent == 'youtube_play':
                self.play(query)
                return f"Playing {query} on YouTube."
            
            elif action == 'search' or intent == 'youtube_search':
                self.search(query)
                return f"Searching for {query} on YouTube."
            
            else:
                return f"Unknown action: {action}"
        
        except YouTubeQueryError as e:
            return f"Query error: {str(e)}"

    def _handle_player_control(self, text: str):
        """Handle player control commands"""
        try:
            # Parse player command
            parsed = parse_player_command(text)
            
            if not parsed:
                return "I didn't understand that player command."
            
            command = parsed.get('command')
            value = parsed.get('value')
            
            print(f"🎮 Player command: {command}, Value: {value}")
            
            # Execute player command
            if command == 'pause':
                self.pause()
                return "Paused."
            
            elif command == 'resume':
                self.resume()
                return "Resumed."
            
            elif command == 'play_pause':
                self.play_pause()
                return "Toggled play/pause."
            
            elif command == 'stop':
                self.stop()
                return "Stopped."
            
            elif command == 'restart':
                self.restart()
                return "Restarted video."
            
            elif command == 'volume_up':
                self.volume_up()
                return "Volume increased."
            
            elif command == 'volume_down':
                self.volume_down()
                return "Volume decreased."
            
            elif command == 'mute':
                self.mute()
                return "Muted."
            
            elif command == 'unmute':
                self.unmute()
                return "Unmuted."
            
            elif command == 'set_volume' and value is not None:
                self.set_volume(value)
                return f"Volume set to {value}%."
            
            elif command == 'seek_forward':
                seconds = value if value else 10
                self.seek_forward(seconds)
                return f"Skipped forward {seconds} seconds."
            
            elif command == 'seek_backward':
                seconds = value if value else 10
                self.seek_backward(seconds)
                return f"Skipped backward {seconds} seconds."
            
            elif command == 'seek_start':
                self.seek_start()
                return "Jumped to start."
            
            elif command == 'seek_end':
                self.seek_end()
                return "Jumped to end."
            
            elif command == 'speed_up':
                self.speed_up()
                return "Speed increased."
            
            elif command == 'speed_down':
                self.speed_down()
                return "Speed decreased."
            
            elif command == 'set_speed' and value is not None:
                self.set_speed(value)
                return f"Playback speed set to {value}x."
            
            elif command == 'fullscreen':
                self.fullscreen()
                return "Entered fullscreen."
            
            elif command == 'exit_fullscreen':
                self.exit_fullscreen()
                return "Exited fullscreen."
            
            elif command == 'theater_mode':
                self.theater_mode()
                return "Toggled theater mode."
            
            elif command == 'captions':
                self.captions()
                return "Toggled captions."
            
            else:
                return f"Unknown player command: {command}"
        
        except Exception as e:
            return f"Player control error: {str(e)}"

    # -------- SEARCH / PLAY --------
    def search(self, query: str):
        search_only(self._driver(), query)

    def play(self, query: str):
        search_and_play_first(self._driver(), query)

    # -------- PLAYER CONTROLS --------
    def play_pause(self):
        YouTubePlayer(self._driver()).play_pause()

    def pause(self):
        YouTubePlayer(self._driver()).pause()

    def resume(self):
        YouTubePlayer(self._driver()).play()

    def stop(self):
        YouTubePlayer(self._driver()).stop()

    def restart(self):
        YouTubePlayer(self._driver()).restart()

    # -------- VOLUME --------
    def volume_up(self):
        YouTubePlayer(self._driver()).volume_up()

    def volume_down(self):
        YouTubePlayer(self._driver()).volume_down()

    def mute(self):
        YouTubePlayer(self._driver()).mute()

    def unmute(self):
        YouTubePlayer(self._driver()).unmute()

    def set_volume(self, level: int):
        """Set volume to specific level (0-100)"""
        YouTubePlayer(self._driver()).set_volume(level)

    # -------- SEEK --------
    def seek_forward(self, seconds=10):
        YouTubePlayer(self._driver()).seek(seconds)

    def seek_backward(self, seconds=10):
        YouTubePlayer(self._driver()).seek(-seconds)

    def seek_start(self):
        YouTubePlayer(self._driver()).seek_to_start()

    def seek_end(self):
        YouTubePlayer(self._driver()).seek_to_end()

    # -------- SPEED --------
    def speed_up(self):
        YouTubePlayer(self._driver()).speed_up()

    def speed_down(self):
        YouTubePlayer(self._driver()).speed_down()

    def set_speed(self, speed: float):
        YouTubePlayer(self._driver()).set_speed(speed)

    # -------- VIEW --------
    def fullscreen(self):
        YouTubePlayer(self._driver()).fullscreen()

    def exit_fullscreen(self):
        YouTubePlayer(self._driver()).exit_fullscreen()

    def theater_mode(self):
        YouTubePlayer(self._driver()).theater_mode()

    # -------- CAPTIONS --------
    def captions(self):
        YouTubePlayer(self._driver()).toggle_captions()

    def close(self):
        self.session.close()
