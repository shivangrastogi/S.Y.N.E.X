
import logging
import threading
import pyaudio
import asyncio
import queue

logger = logging.getLogger(__name__)

class AudioHandler:
    def __init__(self, websocket_server):
        self.websocket_server = websocket_server
        self.chunk_size = 1024
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16
        
        self.p = pyaudio.PyAudio()
        self.stream_out = None
        self.stream_in = None
        
        self.is_running = False
        self.last_device_id = None
        
        # Buffer for playback to avoid blocking WS loop
        self.playback_queue = queue.Queue()
        
    def start_bridge(self, device_id):
        if self.is_running:
            return
        
        self.is_running = True
        self.last_device_id = device_id
        
        logger.info(f"🎤 Starting Audio Bridge for device: {device_id}")
        
        try:
            # Output stream (Laptop Speaker)
            self.stream_out = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size
            )
            
            # Input stream (Laptop Mic)
            self.stream_in = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # Start threads
            threading.Thread(target=self._mic_capture_loop, daemon=True).start()
            threading.Thread(target=self._playback_loop, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Failed to start audio streams: {e}")
            self.stop_bridge()

    def _mic_capture_loop(self):
        logger.info("📡 Starting Laptop Mic capture loop")
        while self.is_running and self.stream_in:
            try:
                data = self.stream_in.read(self.chunk_size, exception_on_overflow=False)
                if self.last_device_id and self.websocket_server:
                    if self.websocket_server.loop and self.websocket_server.loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.websocket_server.send_to_device_binary(self.last_device_id, data),
                            self.websocket_server.loop
                        )
            except Exception as e:
                logger.error(f"Mic capture error: {e}")
                break

    def _playback_loop(self):
        logger.info("🔊 Starting Playback loop")
        while self.is_running:
            try:
                data = self.playback_queue.get(timeout=1)
                if self.stream_out:
                    self.stream_out.write(data)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Playback error: {e}")

    def handle_mobile_audio(self, data):
        """Receive audio from mobile and queue for playback"""
        if self.is_running:
            self.playback_queue.put(data)

    def stop_bridge(self):
        self.is_running = False
        
        # Clear queue
        with self.playback_queue.mutex:
            self.playback_queue.queue.clear()
            
        if self.stream_out:
            try:
                self.stream_out.stop_stream()
                self.stream_out.close()
            except: pass
        if self.stream_in:
            try:
                self.stream_in.stop_stream()
                self.stream_in.close()
            except: pass
            
        self.stream_out = None
        self.stream_in = None
        logger.info("🛑 Audio Bridge Stopped")

    def __del__(self):
        self.p.terminate()
