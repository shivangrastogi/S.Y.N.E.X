# A.E.R.I.S — Hero-tier Roadmap

**Goal:** turn AERIS from "a desktop chat app that wraps an LLM" into a
showcase Windows-native assistant that *teaches* operating-system concepts
in practice — process supervision, memory pressure handling, IPC, signals,
power state, atomic state, idle detection, sandboxing.

Every phase ships features the user can feel and the engineer can point at
in an interview.

---

## North-star principles

1. **Boot ≤ 5 s on warm cache.** First-paint ≤ 800 ms via splash.
2. **RSS ≤ 1.2 GB at rest.** Sheds caches to ≤ 800 MB under pressure.
3. **Crash-safe.** Power-loss mid-write never corrupts user data.
4. **One process, well-supervised.** Single-instance lock; clean shutdown
   on SIGINT / SIGBREAK / `WM_CLOSE`; auto-restart on segfault.
5. **OS-aware.** Behaviour adapts to battery / idle / DPI / theme /
   foreground-window context.
6. **No silent failures.** Every skill error surfaces in the logs panel
   with a one-line root cause and a "disable this skill" action.

---

## Phase 1 — Foundations (memory + lifecycle)

> OS concept: virtual memory, processes, signals, atomicity.

- **1a. ResourceMonitor** — `core/resource_monitor.py`. Background psutil
  sampler (RSS / CPU / threads / handles) writes to a 1 000-entry ring
  buffer. Emits `memory_pressure(level)` when RSS crosses 1.0 GB
  (warning) / 1.4 GB (critical). Subscribers shed caches.
- **1b. Single-instance lock** — Windows named mutex via `ctypes`. Second
  launch sends `WM_USER` to the first window to focus it, then exits 0.
- **1c. Atomic state writes** — `core/atomic_io.py` (`write_atomic(path,
  data)` → `tempfile + os.replace`). Route `UserMemory`, `settings`,
  `feedback_log` schema-bumps through it.
- **1d. Graceful shutdown** — top-level shutdown manager. Drains
  in-flight brain work, flushes feedback DB, joins worker threads with
  bounded timeout, persists state, exits cleanly on SIGINT / SIGBREAK
  and Qt `aboutToQuit`.
- **1e. Crash recovery beacon** — write a tiny `data/last_boot.json`
  (PID + start time + clean-exit flag). On next boot, if the previous
  run didn't flip the flag, surface a "recovered from crash" banner
  and rotate the crash log.

## Phase 2 — OS integration

> OS concept: window manager, input subsystem, power state, idle detection.

- **2a. System tray** — `QSystemTrayIcon` with status pill (LISTENING /
  IDLE / PROCESSING). Menu: Show/Hide, Mic on/off, Pause, Quit.
  Minimize-to-tray instead of close.
- **2b. Global hotkey** — `Ctrl+Shift+Space` brings window to front and
  arms the mic. Implemented via `keyboard` / win32 `RegisterHotKey`.
- **2c. Native Windows toasts** — `winrt.windows.ui.notifications` for
  reminders, scheduler fires, long-running task complete.
- **2d. Power-aware** — read `psutil.sensors_battery()`. On battery:
  drop `AnimationBus.tick_fast` from 30→15 FPS, raise system-stats poll
  from 2.8 s→6 s, suspend optional vision/gesture engines.
- **2e. Idle detection** — `ctypes` `GetLastInputInfo` polled every 30 s.
  > 5 min idle → pause voice engine + brain prefetch. User activity →
  resume.
- **2f. DPI + theme follow** — listen for Windows light/dark theme
  change; restyle the GUI to match. Per-monitor DPI scaling for HiDPI
  laptops.

## Phase 3 — Brain efficiency

> OS concept: lazy paging, mmap, shared memory.

- **3a. Bounded LRU caches** — `normalizer.clean` (10 k), entity
  gazetteer matches (5 k), recent-query intent cache (256). All caches
  subscribe to `memory_pressure(warning)` → halve size; `critical` →
  clear.
- **3b. Idle encoder unload** — if no query for 5 min, drop the
  sentence-transformer + neural model from RAM. Re-load on demand
  (~3 s) with a "warming up" toast.
- **3c. Quantize the neural intent model** — convert DistilBERT to
  int8 via `torch.ao.quantization` or `optimum.onnxruntime`. Targets
  4× RAM reduction (~530 MB → ~140 MB) at < 2 % accuracy hit.
- **3d. Streaming LLM** — `LLMChat.stream(prompt)` yields tokens as
  they arrive from Ollama; chat panel renders progressively. Cuts
  time-to-first-byte from full-response-wait to ~100 ms.
- **3e. Async skill dispatch** — `ToolRouter` runs handlers in a
  thread pool, not on the brain thread. One slow skill can't block
  others.

## Phase 4 — Reliability

> OS concept: process sandboxing, structured logging, supervisors.

- **4a. Skill circuit breaker** — wrap every skill dispatch with a 5 s
  timeout (per-skill override) + 3-strike auto-disable. Disabled
  skills surface in logs panel with a one-click "re-enable" action.
- **4b. Structured logs** — adopt `structlog` (or hand-roll). Every
  log line carries `module · level · event · context_dict`. Logs
  panel filters by module / level. Rotating file at
  `data/logs/aeris.log` (10 MB × 5).
- **4c. Hot reload** — `skill_registry.reload(name)` re-imports a
  single skill module without restarting AERIS. File-watch
  `skills/` and prompt user to reload changed skills.
- **4d. Health endpoint** — local HTTP server on `127.0.0.1:8765`
  exposing `/health`, `/metrics` (Prometheus-style), `/skills`. Easy
  external monitoring; also lets future mobile companion query state.
- **4e. Crash dump** — on uncaught exception in any worker, write
  thread dump + last 50 log lines to `data/logs/crash_<ts>.txt`.

## Phase 5 — Hero polish

> OS concept: shell extensions, encrypted storage, user-mode services.

- **5a. In-app settings UI** — full settings page replacing
  hand-editing `data/settings.json`. Live preview, validation, reset.
- **5b. First-run setup wizard** — mic test, voice pick, theme,
  Ollama check, skill enable/disable list.
- **5c. Encrypted memory** — `UserMemory` stored under AES-GCM with
  key derived from Windows DPAPI (machine-bound).
- **5d. Voice biometric gate** — speaker verification before honoring
  high-privilege commands ("delete all", "open vault").
- **5e. Workspace profiles** — detect foreground app (`win32gui`) →
  switch profile (CODING / MEETING / GAMING / IDLE). Profile decides
  which skills are armed and the assistant's verbosity.
- **5f. Self-update** — check GitHub releases on launch (opt-in),
  download + verify signature, schedule replace on next exit.
- **5g. Mobile companion link** — pair the existing `mobile/` Android
  client over LAN. Push notifications, voice commands, mirror chat.

## Phase 6 — Stretch / research

- **6a. ONNX runtime path** — convert MiniLM + DistilBERT to ONNX;
  load via `onnxruntime` CPU EP. Lower RAM, faster cold start.
- **6b. Federated bandit** — share intent-threshold deltas across the
  user's devices (consented) so feedback learning is portable.
- **6c. Rust hot-path extension** — port `HinglishNormalizer` to a
  `pyo3` crate. Calls drop from ~50 µs to < 5 µs.
- **6d. Skill marketplace** — signed plugin format, ratings, sandbox.

---

## Sequencing

```
Phase 1 (foundations)  -> Phase 2 (OS integration)
                       \-> Phase 3 (brain efficiency, parallel)
Phase 4 (reliability)  -> builds on 1+3
Phase 5 (polish)       -> after 1-4 stable
Phase 6 (research)     -> opportunistic
```

The first three phases are the load-bearing ones — everything in 4-6
assumes the resource monitor and shutdown manager from phase 1 exist.

## Measuring success

Each phase has a one-line acceptance metric on the PR that ships it:

| Phase | Metric                                                   |
|-------|----------------------------------------------------------|
| 1     | RSS plateau ≤ 1.2 GB after 60 min idle; crash test passes |
| 2     | Tray + hotkey work; idle battery RSS drops ≥ 20 %         |
| 3     | RSS at rest drops ≥ 30 %; first-token LLM ≤ 150 ms        |
| 4     | No skill failure can wedge the GUI; logs filterable       |
| 5     | New user can do mic test + first command without docs     |
| 6     | Cold-boot drops to ≤ 3 s with ONNX path                   |
