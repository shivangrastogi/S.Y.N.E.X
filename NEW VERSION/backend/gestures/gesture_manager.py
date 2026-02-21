# BACKEND/gestures/gesture_manager.py
import ctypes

import cv2
import time

from BACKEND.gestures.camera.camera_stream import CameraStream
from BACKEND.gestures.detection.hand_tracker import hands, mp_draw, HAND_CONNECTIONS
from BACKEND.gestures.detection.gesture_classifier import classify_raw_gesture
from BACKEND.gestures.detection.gesture_smoother import smooth_gesture
from BACKEND.gestures.gesture_engine import GestureEngine
from BACKEND.gestures.gestures.index_swipe import IndexSwipeController
from BACKEND.gestures.ui.overlay import draw_volume_ui
from BACKEND.gestures.ui.hud import draw_status

def move_window_bottom_right(window_name, width, height, margin=20):
    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    x = screen_width - width - margin
    y = screen_height - height - margin

    cv2.moveWindow(window_name, x, y)

class GestureManager:
    def __init__(
        self,
        on_exit=None,
        on_toggle=None,
        on_status=None,
        on_frame=None,
        on_event=None,
        active=False,
        show_ui=False,
        toggle_hold_seconds=2.0,
        frame_interval=0.1,
        status_interval=0.2,
    ):
        self.engine = GestureEngine()
        self.engine.active = active
        self.camera = CameraStream()
        self.index_swipe = IndexSwipeController()
        self.on_exit = on_exit
        self.on_toggle = on_toggle
        self.on_status = on_status
        self.on_frame = on_frame
        self.on_event = on_event
        self.running = True
        self.show_ui = show_ui
        self.toggle_hold_seconds = toggle_hold_seconds
        self._v_sign_start = None
        self._v_sign_triggered = False
        self.frame_interval = frame_interval
        self.status_interval = status_interval
        self._last_frame_emit = 0.0
        self._last_status_emit = 0.0
        self._fps_frames = 0
        self._fps_last_time = time.time()
        self._fps = 0.0
        self._last_gesture_event = "NONE"
        self._last_status_active = None
        self._last_status_gesture = None
        self._last_hand_crop = None

    def _build_no_hand_frame(self, frame):
        """Return a black frame with a red warning when no hand is detected."""
        try:
            h, w, _ = frame.shape
            blank = frame.copy()
            blank[:] = (0, 0, 0)
            msg = "NO HAND DETECTED"
            (text_w, text_h), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
            x = max(12, (w - text_w) // 2)
            y = max(text_h + 12, h // 2)
            cv2.putText(
                blank,
                msg,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.1,
                (0, 0, 220),
                3,
                cv2.LINE_AA,
            )
            return blank
        except Exception:
            return frame

    def _compute_hand_crop(self, frame, lm):
        """Draw styled hand overlay on full frame without cropping.
        Draws neon-style connections and points.
        """
        try:
            display = frame.copy()
            h, w, _ = display.shape

            overlay = display.copy()
            line_color = (255, 205, 100)  # warm neon
            point_color = (0, 240, 255)   # cyan neon
            thick = 2
            circ_r = 3

            # Draw connections
            for a, b in HAND_CONNECTIONS:
                ax = int(lm.landmark[a].x * w)
                ay = int(lm.landmark[a].y * h)
                bx = int(lm.landmark[b].x * w)
                by = int(lm.landmark[b].y * h)
                cv2.line(overlay, (ax, ay), (bx, by), line_color, thick, cv2.LINE_AA)

            # Draw points
            for p in lm.landmark:
                px = int(p.x * w)
                py = int(p.y * h)
                cv2.circle(overlay, (px, py), circ_r, point_color, -1, cv2.LINE_AA)

            # Blend overlay
            display = cv2.addWeighted(overlay, 0.75, display, 0.25, 0)
            return display
        except Exception:
            return None

    def set_active(self, active: bool, show_ui: bool | None = None):
        self.engine.active = active
        if show_ui is not None:
            self.show_ui = show_ui
            if not self.show_ui:
                cv2.destroyAllWindows()

    def stop(self):
        self.running = False

    def run(self):
        WINDOW_NAME = "Gesture System"
        try:
            while self.running:
                now = time.time()
                ret, frame = self.camera.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                frame_width = frame.shape[1]

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)

                gesture = "NONE"
                lock_progress = 0.0
                volume_percent = None
                swipe_text = None

                preview_frame = None

                if result.multi_hand_landmarks:
                    lm = result.multi_hand_landmarks[0]

                    mp_draw.draw_landmarks(frame, lm, HAND_CONNECTIONS)

                    raw = classify_raw_gesture(lm)
                    gesture = smooth_gesture(raw)

                    # Build hand-only cropped preview
                    hand_crop = self._compute_hand_crop(frame, lm)
                    if hand_crop is not None:
                        self._last_hand_crop = hand_crop
                        preview_frame = hand_crop
                    else:
                        preview_frame = frame

                    # =================================
                    # ✌️ V SIGN (HOLD TO TOGGLE MODE)
                    # =================================
                    if raw == "V_SIGN" or gesture == "V_SIGN":
                        now = time.time()
                        if self._v_sign_start is None:
                            self._v_sign_start = now
                        elif (now - self._v_sign_start) >= self.toggle_hold_seconds:
                            if not self._v_sign_triggered:
                                self._v_sign_triggered = True
                                self._v_sign_start = None
                                if self.on_toggle:
                                    self.on_toggle()
                    else:
                        self._v_sign_start = None
                        self._v_sign_triggered = False

                    # =================================
                    # ☝️ INDEX HOLD → SWIPE MODE
                    # =================================
                    if raw == "INDEX_ONLY" and self.engine.active:
                        swipe_text, _ = self.index_swipe.update(lm, frame_width)
                    else:
                        self.index_swipe.reset()

                    if self.engine.active:
                        # =================================
                        # ✊ FIST → LOCK
                        # =================================
                        if gesture == "FIST":
                            lock_progress, _ = self.engine.update("FIST", lm)

                        # =================================
                        # 🔊 VOLUME PINCH
                        # =================================
                        if gesture == "VOLUME_PINCH":
                            _, volume_percent = self.engine.update("VOLUME_PINCH", lm)

                    # ---------- VOLUME UI ----------
                    if volume_percent is not None:
                        draw_volume_ui(
                            frame,
                            lm.landmark[4],
                            lm.landmark[8],
                            volume_percent
                        )

                    # ---------- LOCK UI ----------
                    if raw == "FIST" and lock_progress > 0:
                        h, w, _ = frame.shape
                        cv2.putText(
                            frame,
                            f"LOCKING {int(lock_progress * 100)}%",
                            (w // 2 - 150, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.2,
                            (0, 0, 255),
                            3
                        )

                    # ---------- SWIPE PROMPT ----------
                    if swipe_text:
                        h, w, _ = frame.shape
                        cv2.rectangle(frame, (0, h - 70), (w, h), (25, 25, 25), -1)
                        cv2.putText(
                            frame,
                            swipe_text,
                            (w // 2 - 200, h - 25),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 255, 255),
                            3
                        )

                else:
                    self._last_hand_crop = None
                    preview_frame = self._build_no_hand_frame(frame)

                # Emit gesture event updates
                if self.on_event and gesture not in ("NONE", "TRANSITIONING"):
                    if gesture != self._last_gesture_event:
                        self._last_gesture_event = gesture
                        self.on_event(gesture)

                # FPS tracking
                self._fps_frames += 1
                if now - self._fps_last_time >= 1.0:
                    self._fps = self._fps_frames / (now - self._fps_last_time)
                    self._fps_frames = 0
                    self._fps_last_time = now

                # Emit status updates
                should_emit_status = False
                if self.engine.active != self._last_status_active:
                    should_emit_status = True
                if gesture != self._last_status_gesture and gesture not in ("NONE", "TRANSITIONING"):
                    should_emit_status = True
                if self.engine.active and (now - self._last_status_emit) >= self.status_interval:
                    should_emit_status = True

                if self.on_status and should_emit_status:
                    self._last_status_emit = now
                    self._last_status_active = self.engine.active
                    self._last_status_gesture = gesture
                    self.on_status(self.engine.active, gesture, self._fps)

                # Emit preview frames (always, even when inactive)
                # This ensures the UI panel shows live camera feed
                if self.on_frame and (now - self._last_frame_emit) >= self.frame_interval:
                    self._last_frame_emit = now
                    # Prefer cropped hand preview when available, otherwise fallback frame
                    if preview_frame is not None:
                        to_emit = preview_frame
                    elif self._last_hand_crop is not None:
                        to_emit = self._last_hand_crop
                    else:
                        to_emit = frame
                    self.on_frame(to_emit)

                if self.show_ui:
                    draw_status(frame, self.engine.active, gesture)
                    cv2.imshow(WINDOW_NAME, frame)

                # Move window once (after first frame)
                if self.show_ui and not hasattr(self, "_window_positioned"):
                    h, w, _ = frame.shape
                    move_window_bottom_right(WINDOW_NAME, w, h)
                    self._window_positioned = True

                if self.show_ui:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                else:
                    time.sleep(0.01)
        finally:
            self.camera.release()
            cv2.destroyAllWindows()

            if self.on_exit:
                self.on_exit()
