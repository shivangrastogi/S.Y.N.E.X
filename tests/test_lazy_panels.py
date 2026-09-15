"""RightPanelStack builds panels on first view, not at boot (§4.1).

Offscreen Qt, same fixture style as test_routine_builder. The expensive
panels are never constructed here — every test that needs a "panel" swaps in
a trivial factory, so the suite pays none of the 5.4 s this change removes
from boot.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def qapp(qt_app):
    """Session-wide QApplication (see tests/conftest.py `qt_app`).

    Must not create its own: a per-module QApplication is destroyed at module
    teardown, taking the animation-bus singleton's C++ object with it.
    """
    yield qt_app


@pytest.fixture
def stack(qapp, monkeypatch):
    """A stack whose every lazy panel is a cheap stub.

    The real factories are replaced *after* construction, which is safe
    precisely because construction builds none of them — if that ever
    regresses, `test_nothing_is_built_at_boot` fails first.
    """
    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtWidgets import QWidget
    from ui.jarvis_v31.tab_panels import RightPanelStack

    class _Stub(QWidget):
        submit_text = pyqtSignal(str)
        use_phrase = pyqtSignal(str)

        def __init__(self, idx):
            super().__init__()
            self.idx = idx
            self.refreshed = 0

        def refresh(self):
            self.refreshed += 1

    s = RightPanelStack()
    built = []

    def _factory(i):
        def _make():
            built.append(i)
            return _Stub(i)
        return _make

    s._factories = {i: _factory(i) for i in s._factories}
    s.built_log = built
    return s


class TestBootCost:
    def test_nothing_is_built_at_boot(self, qapp):
        """The point of the change: opening AERIS builds no tab panel."""
        from ui.jarvis_v31.tab_panels import RightPanelStack
        s = RightPanelStack()
        assert s._built == {}

    def test_chat_panel_is_eager(self, qapp):
        """Chat is the landing tab — it must exist immediately."""
        from ui.jarvis_v31.tab_panels import RightPanelStack
        s = RightPanelStack()
        assert s.chat_panel is not None

    def test_every_slot_is_occupied(self, qapp):
        """Placeholders keep the stack the right size so _TAB_INDEX holds."""
        from ui.jarvis_v31.tab_panels import RightPanelStack, _TAB_INDEX
        s = RightPanelStack()
        assert s._stack.count() == max(_TAB_INDEX.values()) + 1


class TestLazyBuild:
    def test_switching_builds_only_that_panel(self, stack):
        stack.switch_tab("system")
        assert stack.built_log == [4]

    def test_a_panel_is_built_at_most_once(self, stack):
        for _ in range(5):
            stack.switch_tab("system")
        assert stack.built_log == [4]

    def test_switching_back_and_forth_builds_two(self, stack):
        stack.switch_tab("system")
        stack.switch_tab("memory")
        stack.switch_tab("system")
        assert sorted(stack.built_log) == [3, 4]

    def test_chat_builds_nothing(self, stack):
        stack.switch_tab("chat")
        assert stack.built_log == []

    def test_auto_tab_builds_nothing(self, stack):
        """'auto' aliases index 1 — automation chips live inside chat."""
        stack.switch_tab("auto")
        assert stack.built_log == []

    def test_unknown_key_falls_back_to_chat(self, stack):
        stack.switch_tab("nonsense")
        assert stack._stack.currentIndex() == 1
        assert stack.built_log == []


class TestIndexIntegrity:
    def test_every_key_lands_on_its_own_index(self, stack):
        """A lazy swap must not shift the stack — _TAB_INDEX is the map the
        floating dock navigates by."""
        from ui.jarvis_v31.tab_panels import _TAB_INDEX
        for key, idx in _TAB_INDEX.items():
            stack.switch_tab(key)
            assert stack._stack.currentIndex() == idx, key

    def test_the_built_panel_lands_at_its_own_index(self, stack):
        stack.switch_tab("trust")
        assert stack._stack.widget(11) is stack._built[11]
        assert stack._built[11].idx == 11

    def test_building_one_panel_does_not_disturb_neighbours(self, stack):
        before = [stack._stack.widget(i) for i in range(15)]
        stack.switch_tab("vision")                     # index 6
        after = [stack._stack.widget(i) for i in range(15)]
        for i in range(15):
            if i == 6:
                assert after[i] is not before[i]       # swapped
            else:
                assert after[i] is before[i], i        # untouched


class TestNamedAccessors:
    @pytest.mark.parametrize("attr,idx", [
        ("routines_panel", 8), ("notifications_panel", 9),
        ("quick_panel", 10), ("trust_panel", 11),
        ("abilities_panel", 12), ("intel_panel", 13),
        ("continuity_panel", 14),
    ])
    def test_accessor_builds_on_demand(self, stack, attr, idx):
        assert stack.built_log == []
        panel = getattr(stack, attr)
        assert panel is not None
        assert stack.built_log == [idx]

    def test_accessor_is_stable_across_calls(self, stack):
        assert stack.trust_panel is stack.trust_panel
        assert stack.built_log == [11]


class TestPeek:
    def test_peek_does_not_construct(self, stack):
        assert stack.peek("routines") is None
        assert stack.built_log == []

    def test_peek_returns_a_built_panel(self, stack):
        stack.switch_tab("routines")
        assert stack.peek("routines") is stack._built[8]

    def test_peek_on_an_unknown_key(self, stack):
        assert stack.peek("nonsense") is None


class TestSignalRelays:
    def test_quick_submit_relays_after_the_panel_is_built(self, stack):
        seen = []
        stack.quick_submit_text.connect(seen.append)
        stack.switch_tab("quick")
        stack._built[10].submit_text.emit("hello")
        assert seen == ["hello"]

    def test_abilities_use_phrase_relays(self, stack):
        seen = []
        stack.abilities_use_phrase.connect(seen.append)
        stack.switch_tab("abilities")
        stack._built[12].use_phrase.emit("time kya hai")
        assert seen == ["time kya hai"]

    def test_connecting_a_relay_does_not_build_the_panel(self, stack):
        """The whole reason relays exist: main_window connects these at
        boot, and that must not construct the panels."""
        stack.quick_submit_text.connect(lambda _t: None)
        stack.abilities_use_phrase.connect(lambda _t: None)
        assert stack.built_log == []

    def test_relay_survives_the_accessor_path_too(self, stack):
        seen = []
        stack.quick_submit_text.connect(seen.append)
        stack.quick_panel.submit_text.emit("via accessor")
        assert seen == ["via accessor"]


class TestBrokenPanel:
    def test_a_failing_panel_does_not_break_the_window(self, stack):
        def _boom():
            raise RuntimeError("panel is broken")

        stack._factories[4] = _boom
        stack.switch_tab("system")                 # must not raise
        assert stack._stack.currentIndex() == 4    # tab still switches
        assert stack.peek("system") is None

    def test_a_failing_panel_is_not_retried_on_every_click(self, stack):
        calls = []

        def _boom():
            calls.append(1)
            raise RuntimeError("nope")

        stack._factories[4] = _boom
        for _ in range(5):
            stack.switch_tab("system")
        assert len(calls) == 1                     # factory dropped

    def test_other_panels_still_build_after_one_fails(self, stack):
        stack._factories[4] = lambda: (_ for _ in ()).throw(RuntimeError())
        stack.switch_tab("system")
        stack.switch_tab("memory")
        assert stack.peek("memory") is not None
