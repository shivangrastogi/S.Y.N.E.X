"""Background reminder scheduler — wraps APScheduler with a tiny API.

Reminders persist in memory only by default; pass ``persistent=True`` to
keep them across restarts via SQLAlchemy job store.

The scheduler thread fires the callback (typically TTS speak) at the
scheduled time. Reminders that fire successfully are removed automatically.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class ScheduledReminder:
    job_id: str
    message: str
    fire_at: datetime


class ReminderScheduler:
    def __init__(self, on_fire: Callable[[str], None], *, persistent: bool = False,
                 store_path: Optional[str] = None):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError as e:
            raise ImportError(
                "APScheduler not installed. Run: pip install apscheduler"
            ) from e

        if persistent and store_path:
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
            os.makedirs(os.path.dirname(store_path), exist_ok=True)
            jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{store_path}")}
            self._sched = BackgroundScheduler(jobstores=jobstores, daemon=True)
        else:
            self._sched = BackgroundScheduler(daemon=True)

        self._on_fire = on_fire
        self._sched.start()

    # ------------------------------------------------------------------ #
    #  API                                                                #
    # ------------------------------------------------------------------ #

    def schedule(self, message: str, fire_at: datetime) -> ScheduledReminder:
        """Add a one-shot reminder. Returns the scheduled reminder descriptor."""
        if fire_at <= datetime.now():
            raise ValueError("Reminder time is in the past.")
        job_id = f"rem_{int(fire_at.timestamp())}_{abs(hash(message)) % 10000}"
        self._sched.add_job(
            self._fire,
            trigger="date",
            run_date=fire_at,
            args=[message],
            id=job_id,
            replace_existing=True,
        )
        log.info("[Scheduler] Reminder added: %r at %s", message, fire_at)
        return ScheduledReminder(job_id=job_id, message=message, fire_at=fire_at)

    def list_upcoming(self) -> list[ScheduledReminder]:
        out: list[ScheduledReminder] = []
        for job in self._sched.get_jobs():
            if job.next_run_time:
                msg = job.args[0] if job.args else "(no message)"
                out.append(ScheduledReminder(
                    job_id=job.id,
                    message=msg,
                    fire_at=job.next_run_time.replace(tzinfo=None),
                ))
        return sorted(out, key=lambda r: r.fire_at)

    def cancel(self, job_id: str) -> bool:
        try:
            self._sched.remove_job(job_id)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        try:
            self._sched.shutdown(wait=False)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Internals                                                          #
    # ------------------------------------------------------------------ #

    def _fire(self, message: str) -> None:
        try:
            self._on_fire(message)
        except Exception as e:
            log.exception("[Scheduler] reminder callback raised: %s", e)
