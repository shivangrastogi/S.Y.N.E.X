
import pyaudio
import threading
import queue
import logging

class AudioBridge:
    def __init__(self, callback_send_func):
        self.p = pyaudio.PyAudio()
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        
        self.input_stream = None
        self.output_stream = None
        self.is_running = False
        
        self.callback_send = callback_send_func # Function to send data to WS
        self.logger = logging.getLogger("AudioBridge")

    def start(self):
        if self.is_running: return
        self.is_running = True
        
        try:
            # Output Stream (Play received audio)
            self.output_stream = self.p.open(format=self.format,
                                            channels=self.channels,
                                            rate=self.rate,
                                            output=True)
            
            # Input Stream (Capture mic)
            self.input_stream = self.p.open(format=self.format,
                                           channels=self.channels,
                                           rate=self.rate,
                                           input=True,
                                           frames_per_buffer=self.chunk,
                                           stream_callback=self._mic_callback)
                                           
            self.input_stream.start_stream()
            self.logger.info("Audio Bridge Started (Mic + Speaker)")
            
        except Exception as e:
            self.logger.error(f"Failed to start Audio Bridge: {e}")
            self.stop()

    def _mic_callback(self, in_data, frame_count, time_info, status):
        if self.is_running and self.callback_send:
            # Send captured mic data to Android
            self.callback_send(in_data)
        return (None, pyaudio.paContinue)

    def play_audio(self, data):
        if self.is_running and self.output_stream:
            try:
                self.output_stream.write(data)
            except Exception as e:
                self.logger.error(f"Error playing audio: {e}")

    def stop(self):
        self.is_running = False
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        # self.p.terminate() # Keep PyAudio alive for re-use
        self.logger.info("Audio Bridge Stopped")
