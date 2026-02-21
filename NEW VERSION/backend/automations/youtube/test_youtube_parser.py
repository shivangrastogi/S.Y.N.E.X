"""
Unit tests for YouTube query parser
Tests query parsing, player commands, validation, and edge cases
"""

import unittest
from BACKEND.automations.youtube.youtube_query_parser import (
    parse_youtube_query,
    parse_player_command,
    validate_query,
    extract_url_from_text,
    QueryParseError
)


class TestYouTubeQueryParser(unittest.TestCase):
    """Test suite for YouTube query parsing functions"""

    # ==========================================
    # BASIC QUERY PARSING TESTS
    # ==========================================

    def test_basic_play_command(self):
        """Test basic play command parsing"""
        result = parse_youtube_query("play despacito")
        self.assertEqual(result['action'], 'play')
        self.assertEqual(result['query'], 'despacito')

    def test_basic_search_command(self):
        """Test basic search command parsing"""
        result = parse_youtube_query("search for python tutorial")
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['query'], 'python tutorial')

    def test_play_on_youtube(self):
        """Test 'play X on youtube' pattern"""
        result = parse_youtube_query("play shape of you on youtube")
        self.assertEqual(result['action'], 'play')
        self.assertEqual(result['query'], 'shape of you')

    def test_search_youtube_for(self):
        """Test 'search youtube for X' pattern"""
        result = parse_youtube_query("search youtube for react hooks")
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['query'], 'react hooks')

    # ==========================================
    # HINGLISH QUERY TESTS
    # ==========================================

    def test_hinglish_play_command(self):
        """Test Hinglish play command"""
        result = parse_youtube_query("play karo despacito")
        self.assertEqual(result['action'], 'play')
        self.assertEqual(result['query'], 'despacito')

    def test_hinglish_chalao_command(self):
        """Test Hinglish 'chalao' command"""
        result = parse_youtube_query("chalao Justin Bieber")
        self.assertEqual(result['action'], 'play')
        self.assertEqual(result['query'], 'Justin Bieber')

    def test_hinglish_search_command(self):
        """Test Hinglish search command"""
        result = parse_youtube_query("search karo machine learning")
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['query'], 'machine learning')

    def test_hinglish_dhundo_command(self):
        """Test Hinglish 'dhundo' command"""
        result = parse_youtube_query("dhundo nodejs tutorial")
        self.assertEqual(result['action'], 'search')
        self.assertEqual(result['query'], 'nodejs tutorial')

    # ==========================================
    # URL EXTRACTION TESTS
    # ==========================================

    def test_youtube_url_extraction(self):
        """Test extracting YouTube URL from text"""
        text = "play this video https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = parse_youtube_query(text)
        self.assertEqual(result['url'], 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')

    def test_youtu_be_short_url(self):
        """Test extracting youtu.be short URL"""
        text = "play https://youtu.be/dQw4w9WgXcQ"
        result = parse_youtube_query(text)
        self.assertEqual(result['url'], 'https://youtu.be/dQw4w9WgXcQ')

    def test_url_with_timestamp(self):
        """Test URL with timestamp parameter"""
        text = "play https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s"
        result = parse_youtube_query(text)
        self.assertIn('youtube.com/watch', result['url'])

    def test_extract_url_from_text_function(self):
        """Test standalone URL extraction function"""
        text = "Check out this video https://www.youtube.com/watch?v=abc123"
        url = extract_url_from_text(text)
        self.assertEqual(url, 'https://www.youtube.com/watch?v=abc123')

    def test_no_url_in_text(self):
        """Test text without URL returns None"""
        text = "play despacito"
        url = extract_url_from_text(text)
        self.assertIsNone(url)

    # ==========================================
    # PLAYER COMMAND TESTS
    # ==========================================

    def test_pause_command(self):
        """Test pause command parsing"""
        result = parse_player_command("pause the video")
        self.assertEqual(result['command'], 'pause')

    def test_resume_command(self):
        """Test resume/play command parsing"""
        result = parse_player_command("resume")
        self.assertEqual(result['command'], 'resume')

    def test_volume_up_command(self):
        """Test volume up command"""
        result = parse_player_command("increase volume")
        self.assertEqual(result['command'], 'volume_up')

    def test_volume_down_command(self):
        """Test volume down command"""
        result = parse_player_command("decrease volume")
        self.assertEqual(result['command'], 'volume_down')

    def test_volume_set_command(self):
        """Test setting specific volume"""
        result = parse_player_command("set volume to 75")
        self.assertEqual(result['command'], 'set_volume')
        self.assertEqual(result['value'], 75)

    def test_mute_command(self):
        """Test mute command"""
        result = parse_player_command("mute")
        self.assertEqual(result['command'], 'mute')

    def test_unmute_command(self):
        """Test unmute command"""
        result = parse_player_command("unmute")
        self.assertEqual(result['command'], 'unmute')

    def test_skip_forward_command(self):
        """Test skip forward command"""
        result = parse_player_command("skip forward 10 seconds")
        self.assertEqual(result['command'], 'seek_forward')
        self.assertEqual(result['value'], 10)

    def test_skip_backward_command(self):
        """Test skip backward command"""
        result = parse_player_command("go back 30 seconds")
        self.assertEqual(result['command'], 'seek_backward')
        self.assertEqual(result['value'], 30)

    def test_restart_command(self):
        """Test restart video command"""
        result = parse_player_command("restart video")
        self.assertEqual(result['command'], 'restart')

    def test_speed_up_command(self):
        """Test speed up command"""
        result = parse_player_command("speed up")
        self.assertEqual(result['command'], 'speed_up')

    def test_speed_down_command(self):
        """Test slow down command"""
        result = parse_player_command("slow down")
        self.assertEqual(result['command'], 'speed_down')

    def test_set_speed_command(self):
        """Test setting specific playback speed"""
        result = parse_player_command("set speed to 1.5")
        self.assertEqual(result['command'], 'set_speed')
        self.assertEqual(result['value'], 1.5)

    def test_fullscreen_command(self):
        """Test fullscreen command"""
        result = parse_player_command("go fullscreen")
        self.assertEqual(result['command'], 'fullscreen')

    def test_exit_fullscreen_command(self):
        """Test exit fullscreen command"""
        result = parse_player_command("exit fullscreen")
        self.assertEqual(result['command'], 'exit_fullscreen')

    def test_captions_command(self):
        """Test captions toggle command"""
        result = parse_player_command("turn on captions")
        self.assertEqual(result['command'], 'captions')

    # ==========================================
    # VALIDATION TESTS
    # ==========================================

    def test_empty_query_validation(self):
        """Test validation rejects empty query"""
        with self.assertRaises(QueryParseError):
            validate_query("")

    def test_whitespace_only_query_validation(self):
        """Test validation rejects whitespace-only query"""
        with self.assertRaises(QueryParseError):
            validate_query("   ")

    def test_valid_query_validation(self):
        """Test validation accepts valid query"""
        try:
            validate_query("despacito")
            validated = True
        except QueryParseError:
            validated = False
        self.assertTrue(validated)

    def test_minimum_query_length(self):
        """Test query minimum length validation"""
        # Single character should be valid
        try:
            validate_query("a")
            validated = True
        except QueryParseError:
            validated = False
        self.assertTrue(validated)

    # ==========================================
    # EDGE CASE TESTS
    # ==========================================

    def test_query_with_extra_whitespace(self):
        """Test query with extra whitespace is cleaned"""
        result = parse_youtube_query("play    despacito   ")
        self.assertEqual(result['query'].strip(), 'despacito')

    def test_case_insensitive_parsing(self):
        """Test parsing is case insensitive"""
        result1 = parse_youtube_query("PLAY DESPACITO")
        result2 = parse_youtube_query("play despacito")
        self.assertEqual(result1['action'], result2['action'])

    def test_mixed_case_command(self):
        """Test mixed case command parsing"""
        result = parse_youtube_query("PlAy DeSpAcItO")
        self.assertEqual(result['action'], 'play')

    def test_query_with_special_characters(self):
        """Test query with special characters"""
        result = parse_youtube_query("play c++ tutorial")
        self.assertIn('c++', result['query'].lower())

    def test_query_with_numbers(self):
        """Test query with numbers"""
        result = parse_youtube_query("play top 10 songs 2024")
        self.assertIn('2024', result['query'])

    def test_very_long_query(self):
        """Test very long query handling"""
        long_query = "play " + "word " * 100
        result = parse_youtube_query(long_query)
        self.assertEqual(result['action'], 'play')
        self.assertIsNotNone(result['query'])

    def test_query_with_punctuation(self):
        """Test query with punctuation marks"""
        result = parse_youtube_query("play hello, how are you?")
        self.assertIn('hello', result['query'].lower())

    def test_multiple_urls_in_text(self):
        """Test extracting first URL when multiple present"""
        text = "play https://youtube.com/watch?v=1 or https://youtube.com/watch?v=2"
        result = parse_youtube_query(text)
        self.assertIsNotNone(result.get('url'))

    def test_malformed_url(self):
        """Test handling of malformed URL"""
        text = "play htt://not-a-valid-url"
        result = parse_youtube_query(text)
        # Should still parse as regular query
        self.assertIsNotNone(result)

    # ==========================================
    # COMPLEX QUERY TESTS
    # ==========================================

    def test_play_with_artist_and_song(self):
        """Test query with artist and song name"""
        result = parse_youtube_query("play shape of you by ed sheeran")
        self.assertEqual(result['action'], 'play')
        self.assertIn('shape of you', result['query'].lower())
        self.assertIn('ed sheeran', result['query'].lower())

    def test_search_with_filters(self):
        """Test search query with filter words"""
        result = parse_youtube_query("search for python tutorial for beginners")
        self.assertEqual(result['action'], 'search')
        self.assertIn('python tutorial', result['query'].lower())

    def test_youtube_mentioned_multiple_times(self):
        """Test query with 'youtube' mentioned multiple times"""
        result = parse_youtube_query("search youtube for youtube tutorials on youtube")
        self.assertEqual(result['action'], 'search')
        # Should extract query properly

    def test_action_word_in_song_name(self):
        """Test song name containing action words"""
        result = parse_youtube_query("play the song called play")
        # Should handle gracefully

    # ==========================================
    # PLAYER COMMAND EDGE CASES
    # ==========================================

    def test_unknown_player_command(self):
        """Test unknown player command returns None"""
        result = parse_player_command("do something weird")
        self.assertIsNone(result)

    def test_player_command_with_extra_words(self):
        """Test player command with extra words"""
        result = parse_player_command("please pause the video now")
        self.assertEqual(result['command'], 'pause')

    def test_ambiguous_player_command(self):
        """Test ambiguous player command"""
        # Should pick the most specific match
        result = parse_player_command("play pause")
        self.assertIsNotNone(result)

    def test_volume_without_value(self):
        """Test volume command without specific value"""
        result = parse_player_command("set volume")
        # Should return command even if value is missing
        self.assertIsNotNone(result)

    def test_seek_without_duration(self):
        """Test seek command without duration"""
        result = parse_player_command("skip forward")
        self.assertEqual(result['command'], 'seek_forward')
        # Value might be None or default

    # ==========================================
    # INTEGRATION TESTS
    # ==========================================

    def test_parse_then_validate(self):
        """Test parsing followed by validation"""
        result = parse_youtube_query("play despacito")
        query = result.get('query')
        
        try:
            validate_query(query)
            validated = True
        except QueryParseError:
            validated = False
        
        self.assertTrue(validated)

    def test_url_and_query_together(self):
        """Test text with both URL and query"""
        text = "play despacito https://youtube.com/watch?v=abc"
        result = parse_youtube_query(text)
        self.assertIsNotNone(result.get('url'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
