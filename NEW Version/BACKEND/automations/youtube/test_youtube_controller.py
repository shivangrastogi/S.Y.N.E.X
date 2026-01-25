"""
Unit tests for YouTube Controller integration
Tests intent handling, retry logic, and controller integration
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from BACKEND.automations.youtube.yt_controller import YouTubeController


class TestYouTubeController(unittest.TestCase):
    """Test suite for YouTubeController intent handling"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock session to avoid browser initialization
        self.mock_session_patcher = patch('BACKEND.automations.youtube.yt_controller.YouTubeSession')
        self.mock_session = self.mock_session_patcher.start()
        
        # Mock settings
        self.mock_settings_patcher = patch('BACKEND.automations.youtube.yt_controller.YouTubeAutomationSettings')
        self.mock_settings_class = self.mock_settings_patcher.start()
        
        # Configure mock settings instance
        self.mock_settings = MagicMock()
        self.mock_settings.retry.max_attempts = 2
        self.mock_settings.retry.delay = 1
        self.mock_settings.retry.backoff_multiplier = 2.0
        self.mock_settings_class.return_value = self.mock_settings
        
        # Create controller
        self.controller = YouTubeController()

    def tearDown(self):
        """Clean up mocks"""
        self.mock_session_patcher.stop()
        self.mock_settings_patcher.stop()

    # ==========================================
    # INTENT HANDLING TESTS
    # ==========================================

    def test_youtube_play_intent(self):
        """Test handling youtube_play intent"""
        with patch.object(self.controller, '_handle_play_search') as mock_handle:
            mock_handle.return_value = "Playing despacito on YouTube."
            
            result = self.controller.handle('youtube_play', 'play despacito')
            
            mock_handle.assert_called_once_with('youtube_play', 'play despacito')
            self.assertEqual(result, "Playing despacito on YouTube.")

    def test_youtube_search_intent(self):
        """Test handling youtube_search intent"""
        with patch.object(self.controller, '_handle_play_search') as mock_handle:
            mock_handle.return_value = "Searching for python tutorial on YouTube."
            
            result = self.controller.handle('youtube_search', 'search python tutorial')
            
            mock_handle.assert_called_once_with('youtube_search', 'search python tutorial')
            self.assertIn("Searching", result)

    def test_youtube_control_intent(self):
        """Test handling youtube_control intent"""
        with patch.object(self.controller, '_handle_player_control') as mock_handle:
            mock_handle.return_value = "Paused."
            
            result = self.controller.handle('youtube_control', 'pause')
            
            mock_handle.assert_called_once_with('pause')
            self.assertEqual(result, "Paused.")

    def test_unknown_intent(self):
        """Test handling unknown intent"""
        result = self.controller.handle('unknown_intent', 'do something')
        self.assertIn("Unknown YouTube intent", result)

    # ==========================================
    # PLAY/SEARCH HANDLING TESTS
    # ==========================================

    @patch('BACKEND.automations.youtube.yt_controller.parse_youtube_query')
    def test_handle_play_search_with_query(self, mock_parse):
        """Test _handle_play_search with valid query"""
        mock_parse.return_value = {
            'action': 'play',
            'query': 'despacito'
        }
        
        with patch.object(self.controller, 'play') as mock_play:
            result = self.controller._handle_play_search('youtube_play', 'play despacito')
            
            mock_parse.assert_called_once_with('play despacito')
            mock_play.assert_called_once_with('despacito')
            self.assertIn("Playing", result)
            self.assertIn("despacito", result)

    @patch('BACKEND.automations.youtube.yt_controller.parse_youtube_query')
    def test_handle_play_search_empty_query(self, mock_parse):
        """Test _handle_play_search with empty query"""
        mock_parse.return_value = {'query': None}
        
        result = self.controller._handle_play_search('youtube_play', 'play')
        
        self.assertIn("What should I play", result)

    @patch('BACKEND.automations.youtube.yt_controller.parse_youtube_query')
    def test_handle_search_action(self, mock_parse):
        """Test search action handling"""
        mock_parse.return_value = {
            'action': 'search',
            'query': 'python tutorial'
        }
        
        with patch.object(self.controller, 'search') as mock_search:
            result = self.controller._handle_play_search('youtube_search', 'search python tutorial')
            
            mock_search.assert_called_once_with('python tutorial')
            self.assertIn("Searching", result)

    # ==========================================
    # PLAYER CONTROL TESTS
    # ==========================================

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_pause_command(self, mock_parse):
        """Test pause command handling"""
        mock_parse.return_value = {'command': 'pause', 'value': None}
        
        with patch.object(self.controller, 'pause') as mock_pause:
            result = self.controller._handle_player_control('pause')
            
            mock_pause.assert_called_once()
            self.assertEqual(result, "Paused.")

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_resume_command(self, mock_parse):
        """Test resume command handling"""
        mock_parse.return_value = {'command': 'resume', 'value': None}
        
        with patch.object(self.controller, 'resume') as mock_resume:
            result = self.controller._handle_player_control('resume')
            
            mock_resume.assert_called_once()
            self.assertEqual(result, "Resumed.")

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_volume_up_command(self, mock_parse):
        """Test volume up command handling"""
        mock_parse.return_value = {'command': 'volume_up', 'value': None}
        
        with patch.object(self.controller, 'volume_up') as mock_volume_up:
            result = self.controller._handle_player_control('increase volume')
            
            mock_volume_up.assert_called_once()
            self.assertEqual(result, "Volume increased.")

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_set_volume_command(self, mock_parse):
        """Test set volume command with value"""
        mock_parse.return_value = {'command': 'set_volume', 'value': 75}
        
        with patch.object(self.controller, 'set_volume') as mock_set_volume:
            result = self.controller._handle_player_control('set volume to 75')
            
            mock_set_volume.assert_called_once_with(75)
            self.assertIn("75", result)

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_seek_forward_command(self, mock_parse):
        """Test seek forward command"""
        mock_parse.return_value = {'command': 'seek_forward', 'value': 10}
        
        with patch.object(self.controller, 'seek_forward') as mock_seek:
            result = self.controller._handle_player_control('skip forward 10 seconds')
            
            mock_seek.assert_called_once_with(10)
            self.assertIn("10", result)

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_fullscreen_command(self, mock_parse):
        """Test fullscreen command"""
        mock_parse.return_value = {'command': 'fullscreen', 'value': None}
        
        with patch.object(self.controller, 'fullscreen') as mock_fullscreen:
            result = self.controller._handle_player_control('go fullscreen')
            
            mock_fullscreen.assert_called_once()
            self.assertEqual(result, "Entered fullscreen.")

    @patch('BACKEND.automations.youtube.yt_controller.parse_player_command')
    def test_handle_unknown_player_command(self, mock_parse):
        """Test unknown player command"""
        mock_parse.return_value = None
        
        result = self.controller._handle_player_control('do something weird')
        
        self.assertIn("didn't understand", result)

    # ==========================================
    # RETRY LOGIC TESTS
    # ==========================================

    def test_retry_on_failure(self):
        """Test retry logic on failure"""
        call_count = {'count': 0}
        
        def failing_handle(*args):
            call_count['count'] += 1
            if call_count['count'] < 2:
                raise Exception("Temporary failure")
            return "Success"
        
        with patch.object(self.controller, '_handle_play_search', side_effect=failing_handle):
            with patch('time.sleep'):  # Mock sleep to speed up test
                result = self.controller.handle('youtube_play', 'play despacito')
                
                self.assertEqual(call_count['count'], 2)
                self.assertEqual(result, "Success")

    def test_max_retries_exceeded(self):
        """Test max retries exceeded returns error"""
        with patch.object(self.controller, '_handle_play_search', side_effect=Exception("Persistent failure")):
            with patch('time.sleep'):
                result = self.controller.handle('youtube_play', 'play despacito')
                
                self.assertIn("Failed to execute", result)
                self.assertIn("2 attempts", result)

    def test_exponential_backoff(self):
        """Test exponential backoff timing"""
        with patch.object(self.controller, '_handle_play_search', side_effect=Exception("Error")):
            with patch('time.sleep') as mock_sleep:
                self.controller.handle('youtube_play', 'play despacito')
                
                # First retry: delay * backoff^0 = 1 * 2^0 = 1
                # Second retry would be: delay * backoff^1 = 1 * 2^1 = 2
                # But we only get one sleep call since max_attempts=2
                self.assertEqual(mock_sleep.call_count, 1)

    # ==========================================
    # INTEGRATION TESTS
    # ==========================================

    def test_full_play_flow(self):
        """Test complete play flow from intent to execution"""
        with patch('BACKEND.automations.youtube.yt_controller.parse_youtube_query') as mock_parse:
            mock_parse.return_value = {'action': 'play', 'query': 'despacito'}
            
            with patch.object(self.controller, 'play') as mock_play:
                result = self.controller.handle('youtube_play', 'play despacito')
                
                mock_parse.assert_called_once()
                mock_play.assert_called_once_with('despacito')
                self.assertIn("Playing", result)

    def test_full_control_flow(self):
        """Test complete control flow from intent to execution"""
        with patch('BACKEND.automations.youtube.yt_controller.parse_player_command') as mock_parse:
            mock_parse.return_value = {'command': 'pause', 'value': None}
            
            with patch.object(self.controller, 'pause') as mock_pause:
                result = self.controller.handle('youtube_control', 'pause')
                
                mock_parse.assert_called_once()
                mock_pause.assert_called_once()
                self.assertEqual(result, "Paused.")

    def test_error_handling(self):
        """Test error handling in controller"""
        with patch.object(self.controller, '_handle_play_search', side_effect=Exception("Test error")):
            with patch('time.sleep'):
                result = self.controller.handle('youtube_play', 'play despacito')
                
                self.assertIn("Failed to execute", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
