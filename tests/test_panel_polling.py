"""Panels stop working when nobody is looking at them (§4.1).

Two mechanisms, both tested here:

  * `_GlassPanel._gated_timer` — QTimers that stop on hide, restart on show.
  * an `isVisible()` guard on the `tick_slow` handlers, which ride a shared
    animation bus and so cannot be stopped the same way.

Plus WorkbookPanel's read moving off the GUI thread.
"""

from __future__ import annotations

import os
import time

import pytest


@pytest.fixture(scope="module")
def qapp(qt_app):
    """Session-wide QApplication (see tests/conftest.py `qt_app`).

    Must not create its own: a per-module QApplication is destroyed at module
    teardown, taking the animation-bus singleton's C++ object with it.
    """
    yield qt_app


@pytest.fixture
def panel(qapp):
    """A bare _GlassPanel with one gated timer and a fire counter."""
    from ui.jarvis_v31.tab_panels import _GlassPanel

    class _P(_GlassPanel):
        def __init__(self):
            super().__init__()
            self.fires = 0
            self.timer = self._gated_timer(50, self._on_tick)

        def _on_tick(self):
            self.fires += 1

    return _P()


class TestGatedTimer:
    def test_not_started_until_shown(self, panel):
        """A panel built but never opened must never poll — otherwise the
        lazy-build win of §6.20 leaks straight back out."""
        assert panel.timer.isActive() is False
        assert panel.fires == 0

    def test_starts_on_show(self, panel):
        panel.show()
        assert panel.timer.isActive() is True

    def test_fires_once_immediately_on_show(self, panel):
        """Without this a Trust panel would show up to 30 s of staleness on
        open, because its poll had been paused."""
        panel.show()
        assert panel.fires == 1

    def test_stops_on_hide(self, panel):
        panel.show()
        panel.hide()
        assert panel.timer.isActive() is False

    def test_no_ticks_accumulate_while_hidden(self, qapp, panel):
        panel.show()
        panel.hide()
        before = panel.fires
        deadline = time.monotonic() + 0.3      # 6x the 50 ms interval
        while time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert panel.fires == before

    def test_ticks_resume_after_reshow(self, qapp, panel):
        panel.show(); panel.hide()
        before = panel.fires
        panel.show()
        assert panel.fires == before + 1       # the immediate fire
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline and panel.fires <= before + 1:
            qapp.processEvents()
            time.sleep(0.01)
        assert panel.fires > before + 1        # and the timer is running

    def test_reshow_does_not_double_start(self, panel):
        panel.show()
        panel.show()
        assert panel.timer.isActive() is True   # still exactly one timer


class TestRealPanelsAreGated:
    @pytest.mark.parametrize("cls_name", ["VisionPanel", "TrustPanel"])
    def test_panel_registers_a_gated_timer(self, qapp, cls_name):
        from ui.jarvis_v31 import tab_panels as tp
        p = getattr(tp, cls_name)()
        assert p._gated, f"{cls_name} has no gated timer"
        assert all(not t.isActive() for t in p._gated), \
            f"{cls_name} polls before being shown"

    def test_workbook_is_gated(self, qapp):
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        assert p._poll.isActive() is False

    def test_gating_follows_the_stack(self, qapp):
        """End to end through the real stack: switching tabs must start and
        stop the panel's polling."""
        from ui.jarvis_v31.tab_panels import RightPanelStack
        s = RightPanelStack()
        s.show()
        s.switch_tab("vision")
        qapp.processEvents()
        v = s.peek("vision")
        assert v._poll.isActive() is True
        s.switch_tab("chat")
        qapp.processEvents()
        assert v._poll.isActive() is False
        s.switch_tab("vision")
        qapp.processEvents()
        assert v._poll.isActive() is True

    def test_hiding_the_window_stops_polling(self, qapp):
        """A minimised AERIS should poll nothing."""
        from ui.jarvis_v31.tab_panels import RightPanelStack
        s = RightPanelStack()
        s.show()
        s.switch_tab("vision")
        qapp.processEvents()
        v = s.peek("vision")
        assert v._poll.isActive() is True
        s.hide()
        qapp.processEvents()
        assert v._poll.isActive() is False


class TestTickSlowGuard:
    """`tick_slow` handlers check visibility rather than being stopped."""

    def test_home_panel_skips_while_hidden(self, qapp, monkeypatch):
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.HomePanel()
        calls = []
        monkeypatch.setattr(p, "_refresh", lambda: calls.append(1))
        p._last_refresh = 0.0
        p._maybe_refresh()                     # never shown
        assert calls == []

    def test_home_panel_refreshes_while_visible(self, qapp, monkeypatch):
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.HomePanel()
        p.show()
        calls = []
        monkeypatch.setattr(p, "_refresh", lambda: calls.append(1))
        p._last_refresh = 0.0
        p._maybe_refresh()
        assert calls == [1]

    def test_suggestions_panel_skips_while_hidden(self, qapp, monkeypatch):
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.SmartSuggestionsPanel()
        calls = []
        monkeypatch.setattr(p, "_refresh", lambda: calls.append(1))
        p._last_refresh = 0.0
        p._maybe_refresh()
        assert calls == []


class TestWorkbookOffThread:
    def test_read_returns_data_without_touching_widgets(self, qapp):
        """`_read_workbook` runs on a worker, so it must be pure I/O — no Qt
        call anywhere in it. If it ever touches a widget this is a crash
        waiting for a slow disk."""
        from ui.jarvis_v31 import tab_panels as tp
        import inspect
        src = inspect.getsource(tp.WorkbookPanel._read_workbook)
        for forbidden in ("self._spend_tile", "self._top_tile",
                          "self._tasks_tile", "self._search_tile",
                          "setText", "findChildren"):
            assert forbidden not in src, \
                f"_read_workbook touches the GUI: {forbidden}"

    def test_read_returns_a_dict(self, qapp):
        from ui.jarvis_v31 import tab_panels as tp
        out = tp.WorkbookPanel()._read_workbook()
        assert isinstance(out, dict)

    def test_apply_stats_paints_the_tiles(self, qapp):
        from PyQt5.QtWidgets import QLabel
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        p._apply_stats({"spend": "₹42", "top": "Food", "tasks": "7",
                        "searches": "3"})
        got = [t.findChildren(QLabel)[0].text() for t in
               (p._spend_tile, p._top_tile, p._tasks_tile, p._search_tile)]
        assert got == ["₹42", "Food", "7", "3"]

    def test_missing_keys_leave_other_tiles_alone(self, qapp):
        """A workbook with no Tasks sheet must not blank the spend tile."""
        from PyQt5.QtWidgets import QLabel
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        p._apply_stats({"spend": "₹42", "top": "Food", "tasks": "7",
                        "searches": "3"})
        p._apply_stats({"spend": "₹99"})       # partial read
        got = [t.findChildren(QLabel)[0].text() for t in
               (p._spend_tile, p._tasks_tile)]
        assert got == ["₹99", "7"]

    def test_refresh_does_not_block_the_gui_thread(self, qapp):
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        t0 = time.perf_counter()
        p._refresh()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # The inline version was 73-96 ms. Generous bound: this asserts the
        # read is not happening here, not a precise timing.
        assert elapsed_ms < 40, f"_refresh blocked for {elapsed_ms:.0f} ms"

    def test_only_one_read_in_flight(self, qapp):
        """A slow disk must not pile up threads behind a 2.5 s timer."""
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        started = []
        p._loading = True                       # pretend one is running
        p._load_and_emit = lambda: started.append(1)
        p._refresh()
        assert started == []

    def test_worker_delivers_to_the_tiles(self, qapp):
        """The real path end to end: kick a read, pump the loop, see data."""
        from PyQt5.QtWidgets import QLabel
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        p._refresh()
        deadline = time.monotonic() + 15
        while p._loading and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.02)
        qapp.processEvents()
        assert p._loading is False
        # Whether the workbook exists on this machine or not, the panel must
        # not have crashed and the tiles must hold strings.
        for tile in (p._spend_tile, p._tasks_tile):
            assert isinstance(tile.findChildren(QLabel)[0].text(), str)

    def test_a_failing_read_clears_the_in_flight_flag(self, qapp):
        """Otherwise one bad read wedges the panel forever."""
        from ui.jarvis_v31 import tab_panels as tp
        p = tp.WorkbookPanel()
        p._read_workbook = lambda: (_ for _ in ()).throw(RuntimeError("disk"))
        p._loading = True
        p._load_and_emit()
        assert p._loading is False
