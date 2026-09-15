"""Split-mode preflight (§6.35) — injected probes, no spawn, no hardware.

The probes are injectable precisely so the *reporting* logic — which flags a
result unlocks, what gets skipped, what the summary claims — is testable
without spending 40 s spawning children.
"""

from __future__ import annotations

from core.split_preflight import (
    FAIL, PASS, SKIP, WARN, Check, Report, check_bus, check_service, run,
)


def _ok_spawn():
    return True, "child answered"


def _bad_spawn():
    return False, "child did not come up"


def _ok_service(_factory_path):
    return True, "child up"


def _bad_service(_factory_path):
    return False, "started, but reports the device stack unavailable"


def _ok_brain():
    """Never let a test import torch for real — that is what injection is for."""
    return True, "all import"


class TestReport:
    def test_a_flag_is_safe_only_when_every_gating_check_passed(self):
        r = Report()
        r.add(Check("a", PASS, unlocks=("F",)))
        r.add(Check("b", PASS, unlocks=("F",)))
        assert r.safe_flags() == ["F"]
        r.add(Check("c", FAIL, unlocks=("F",)))
        assert r.safe_flags() == []

    def test_a_warn_does_not_block_a_flag(self):
        """WARN means degraded, not broken — an absent Vosk still leaves a
        working voice split, just with a different wake-word path."""
        r = Report()
        r.add(Check("optional", WARN, unlocks=("F",)))
        assert r.safe_flags() == ["F"]

    def test_a_skip_blocks_the_flag_it_gates(self):
        """A check that never ran is not evidence that it would have passed."""
        r = Report()
        r.add(Check("x", SKIP, unlocks=("F",)))
        assert r.safe_flags() == []

    def test_failed_lists_only_failures(self):
        r = Report()
        r.add(Check("a", PASS))
        r.add(Check("b", WARN))
        r.add(Check("c", FAIL))
        assert [c.name for c in r.failed()] == ["c"]

    def test_render_shows_every_check_and_the_fix_hints(self):
        r = Report()
        r.add(Check("mediapipe", FAIL, "missing", "pip install mediapipe",
                    ("AERIS_SPLIT_VISION",)))
        out = r.render()
        assert "mediapipe" in out and "pip install mediapipe" in out
        assert "No split flags are safe to enable yet." in out
        assert "1 check(s) failed" in out

    def test_render_names_the_safe_flags(self):
        r = Report()
        r.add(Check("bus", PASS, unlocks=("AERIS_SPLIT_VOICE",)))
        out = r.render()
        assert "Safe to enable:" in out and "AERIS_SPLIT_VOICE" in out

    def test_render_always_points_at_the_real_live_checks(self):
        """Plausibility is not behaviour, and the report must not let that be
        forgotten."""
        out = Report().render()
        assert "run_vision_split.py" in out and "run_voice_split.py" in out


class TestBusCheck:
    def test_a_working_bus_passes_and_unlocks_the_splits(self):
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        c = r.by_name("service bus")
        assert c.status == PASS and "AERIS_SPLIT_VISION" in c.unlocks

    def test_a_dead_bus_fails_with_a_hint(self):
        r = Report()
        check_bus(r, spawn_probe=_bad_spawn)
        c = r.by_name("service bus")
        assert c.status == FAIL and c.fix

    def test_a_raising_probe_is_reported_not_propagated(self):
        def _boom():
            raise RuntimeError("spawn blocked")

        r = Report()
        check_bus(r, spawn_probe=_boom)
        c = r.by_name("service bus")
        assert c.status == FAIL and "spawn blocked" in c.reason
        assert "__main__" in c.fix          # the actual usual cause on Windows


class TestServiceChecks:
    def test_a_healthy_service_passes(self):
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_service(r, "vision service", "x.y", ("AERIS_SPLIT_VISION",),
                      probe=_ok_service)
        assert r.by_name("vision service").status == PASS

    def test_a_service_that_cannot_run_here_fails(self):
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_service(r, "vision service", "x.y", ("AERIS_SPLIT_VISION",),
                      probe=_bad_service)
        assert r.by_name("vision service").status == FAIL

    def test_a_dead_bus_skips_the_service_checks(self):
        """Cheapest-first ordering with skip-on-prerequisite: a machine with no
        working bus should not spend 40 s spawning children to be told the same
        thing five times."""
        called = []

        def _probe(path):
            called.append(path)
            return True, "up"

        r = Report()
        check_bus(r, spawn_probe=_bad_spawn)
        check_service(r, "vision service", "x.y", ("AERIS_SPLIT_VISION",),
                      probe=_probe)
        assert r.by_name("vision service").status == SKIP
        assert called == [], "the probe should not have been run"

    def test_a_skipped_service_leaves_its_flag_unsafe(self):
        r = Report()
        check_bus(r, spawn_probe=_bad_spawn)
        check_service(r, "vision service", "x.y", ("AERIS_SPLIT_VISION",),
                      probe=_ok_service)
        assert "AERIS_SPLIT_VISION" not in r.safe_flags()

    def test_a_raising_probe_names_the_harness_to_run(self):
        def _boom(path):
            raise ImportError("no such factory")

        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_service(r, "voice service", "x.y", ("AERIS_SPLIT_VOICE",),
                      probe=_boom)
        c = r.by_name("voice service")
        assert c.status == FAIL and "run_" in c.fix


class TestEndToEnd:
    def test_run_with_injected_probes_touches_no_hardware(self):
        r = run(spawn_probe=_ok_spawn, service_probe=_ok_service,
                brain_probe=_ok_brain)
        names = [c.name for c in r.checks]
        assert "service bus" in names
        assert "vision service" in names and "voice service" in names
        assert r.render()

    def test_every_check_carries_a_status_the_renderer_understands(self):
        r = run(spawn_probe=_ok_spawn, service_probe=_ok_service,
                brain_probe=_ok_brain)
        assert all(c.status in (PASS, FAIL, WARN, SKIP) for c in r.checks)

    def test_a_failing_import_check_blocks_its_flag(self, monkeypatch):
        import core.split_preflight as sp
        monkeypatch.setattr(sp, "_mod", lambda name: None)
        r = sp.run(spawn_probe=_ok_spawn, service_probe=_ok_service,
                   brain_probe=_ok_brain)
        assert "AERIS_SPLIT_VISION" not in r.safe_flags()
        assert "AERIS_SPLIT_VOICE" not in r.safe_flags()

    def test_optional_libraries_only_warn(self, monkeypatch):
        """Missing Vosk degrades the sleeping-mic path (§6.28); it does not
        stop the voice split working."""
        import core.split_preflight as sp
        monkeypatch.setattr(sp, "_mod",
                            lambda name: None if name == "vosk" else object())
        r = sp.run(spawn_probe=_ok_spawn, service_probe=_ok_service,
                   brain_probe=_ok_brain)
        vosk = r.by_name("vosk (offline STT)")
        assert vosk.status == WARN
        assert "AERIS_SPLIT_VOICE" in r.safe_flags()


class TestBrainStackCheck:
    """`AERIS_SPLIT_BRAIN` used to be reported safe on the strength of the
    *echo* child alone — which proves spawning works, not that torch and
    sentence-transformers import. This project has a documented history of
    exactly that stack breaking on an ABI mismatch while everything else
    stayed fine, so claiming the flag safe without checking it was the same
    overclaim this file exists to prevent elsewhere.
    """

    @staticmethod
    def _ok_brain():
        return True, "all import"

    @staticmethod
    def _bad_brain():
        return False, "1 import(s) failed — sentence_transformers: ValueError"

    def test_a_healthy_stack_unlocks_the_brain_flag(self):
        from core.split_preflight import check_brain_stack
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_brain_stack(r, probe=self._ok_brain)
        c = r.by_name("brain ML stack")
        assert c.status == PASS and c.unlocks == ("AERIS_SPLIT_BRAIN",)

    def test_a_broken_stack_blocks_only_the_brain_flag(self):
        """An ABI break stops the brain child booting; it says nothing about
        vision or voice, which do not touch torch."""
        from core.split_preflight import check_brain_stack
        r = run(spawn_probe=_ok_spawn, service_probe=_ok_service,
                brain_probe=self._bad_brain)
        assert "AERIS_SPLIT_BRAIN" not in r.safe_flags()
        assert "AERIS_SPLIT_VISION" in r.safe_flags()
        assert "AERIS_SPLIT_VOICE" in r.safe_flags()

    def test_a_broken_stack_says_what_to_do(self):
        from core.split_preflight import check_brain_stack
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_brain_stack(r, probe=self._bad_brain)
        c = r.by_name("brain ML stack")
        assert c.status == FAIL and "ABI" in c.fix

    def test_a_dead_bus_skips_it(self):
        from core.split_preflight import check_brain_stack
        called = []
        r = Report()
        check_bus(r, spawn_probe=_bad_spawn)
        check_brain_stack(r, probe=lambda: (called.append(1), (True, "x"))[1])
        assert r.by_name("brain ML stack").status == SKIP and called == []

    def test_a_raising_probe_is_reported(self):
        from core.split_preflight import check_brain_stack

        def _boom():
            raise OSError("no subprocess")

        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        check_brain_stack(r, probe=_boom)
        assert r.by_name("brain ML stack").status == FAIL

    def test_the_brain_flag_is_no_longer_granted_by_the_bus_alone(self):
        """The regression this whole class guards: a passing bus must not be
        sufficient evidence for AERIS_SPLIT_BRAIN."""
        r = Report()
        check_bus(r, spawn_probe=_ok_spawn)
        assert "AERIS_SPLIT_BRAIN" not in r.safe_flags(), (
            "the bus check alone should no longer unlock the brain flag")
