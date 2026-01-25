# BACKEND/automations/youtube/yt_player.py
class YouTubePlayer:
    def __init__(self, driver):
        self.driver = driver

    # ------------------
    # PLAYBACK
    # ------------------
    def play_pause(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.paused ? v.play() : v.pause();
        """)

    def pause(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.pause();
        """)

    def play(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.play();
        """)

    def stop(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.pause();
            v.currentTime = 0;
        """)

    def restart(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.currentTime = 0;
        """)

    # ------------------
    # VOLUME
    # ------------------
    def set_volume(self, value: float):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.volume = arguments[0];
        """, max(0.0, min(1.0, value)))

    def volume_up(self, step=0.1):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.volume = Math.min(1, v.volume + arguments[0]);
        """, step)

    def volume_down(self, step=0.1):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.volume = Math.max(0, v.volume - arguments[0]);
        """, step)

    def mute(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.muted = true;
        """)

    def unmute(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.muted = false;
        """)

    # ------------------
    # SEEKING
    # ------------------
    def seek(self, seconds: int):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.currentTime += arguments[0];
        """, seconds)

    def seek_to_start(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.currentTime = 0;
        """)

    def seek_to_end(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.currentTime = v.duration;
        """)

    # ------------------
    # SPEED
    # ------------------
    def set_speed(self, speed: float):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.playbackRate = arguments[0];
        """, speed)

    def speed_up(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.playbackRate = Math.min(2, v.playbackRate + 0.25);
        """)

    def speed_down(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.playbackRate = Math.max(0.25, v.playbackRate - 0.25);
        """)

    # ------------------
    # VIEW MODES
    # ------------------
    def fullscreen(self):
        self.driver.execute_script("""
            const v = document.querySelector('video');
            if (!v) return;
            v.requestFullscreen();
        """)

    def exit_fullscreen(self):
        self.driver.execute_script("""
            if (document.fullscreenElement) document.exitFullscreen();
        """)

    def theater_mode(self):
        self.driver.execute_script("""
            const el = document.querySelector('ytd-watch-flexy');
            if (!el) return;
            el.setAttribute('theater-requested_', '');
        """)

    # ------------------
    # CAPTIONS
    # ------------------
    def toggle_captions(self):
        self.driver.execute_script("""
            const btn = document.querySelector('.ytp-subtitles-button');
            if (btn) btn.click();
        """)
