"""Smart browser launcher with profile awareness.

Capabilities:
  - Enumerate Chrome / Edge / Brave / Opera profiles from each browser's
    User Data\\Local State JSON.
  - Resolve a browser canonical name from a wide range of user phrasings
    ("brave", "brave browser", "google chrome", "ms edge", "edge browser").
  - Pick a target browser via four-step fallback:
        1. user-named in the command  (e.g. "open X in brave")
        2. assistant default browser  (settings.default_browser)
        3. focused window's browser   (foreground title)
        4. any running browser         (psutil scan)
        5. OS default                  (webbrowser.open)
  - Launch the browser with a URL so Chromium browsers re-use their
    running instance and open the URL as a new tab.
  - Apply a profile directory via --profile-directory="Profile N".
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Optional

from core import settings

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Browser registry                                                           #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class _BrowserSpec:
    canonical: str           # canonical key we use everywhere
    aliases: tuple[str, ...]
    exe_names: tuple[str, ...]  # executable names (no path) for psutil scan
    local_state_paths: tuple[str, ...]  # relative to %LOCALAPPDATA% / %APPDATA%
    fixed_exe_paths: tuple[str, ...]
    is_chromium: bool        # supports --profile-directory


_LOCALAPP = os.environ.get("LOCALAPPDATA", "")
_APPDATA  = os.environ.get("APPDATA", "")
_PROG     = os.environ.get("PROGRAMFILES", r"C:\Program Files")
_PROG86   = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")


_BROWSERS: tuple[_BrowserSpec, ...] = (
    _BrowserSpec(
        canonical="chrome",
        aliases=("chrome", "google chrome", "google-chrome", "gchrome"),
        exe_names=("chrome.exe",),
        local_state_paths=(
            os.path.join(_LOCALAPP, r"Google\Chrome\User Data\Local State"),
        ),
        fixed_exe_paths=(
            os.path.join(_PROG, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(_PROG86, r"Google\Chrome\Application\chrome.exe"),
        ),
        is_chromium=True,
    ),
    _BrowserSpec(
        canonical="edge",
        aliases=("edge", "microsoft edge", "ms edge", "msedge"),
        exe_names=("msedge.exe",),
        local_state_paths=(
            os.path.join(_LOCALAPP, r"Microsoft\Edge\User Data\Local State"),
        ),
        fixed_exe_paths=(
            os.path.join(_PROG86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(_PROG, r"Microsoft\Edge\Application\msedge.exe"),
        ),
        is_chromium=True,
    ),
    _BrowserSpec(
        canonical="brave",
        aliases=("brave", "brave browser", "brave-browser"),
        exe_names=("brave.exe",),
        local_state_paths=(
            os.path.join(_LOCALAPP, r"BraveSoftware\Brave-Browser\User Data\Local State"),
        ),
        fixed_exe_paths=(
            os.path.join(_PROG, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.join(_PROG86, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        ),
        is_chromium=True,
    ),
    _BrowserSpec(
        canonical="opera",
        aliases=("opera", "opera browser"),
        exe_names=("opera.exe",),
        local_state_paths=(),
        fixed_exe_paths=(
            os.path.join(_LOCALAPP, r"Programs\Opera\opera.exe"),
        ),
        is_chromium=True,
    ),
    _BrowserSpec(
        canonical="firefox",
        aliases=("firefox", "mozilla firefox", "ff", "mozilla"),
        exe_names=("firefox.exe",),
        local_state_paths=(),  # Firefox uses different profile mechanism
        fixed_exe_paths=(
            os.path.join(_PROG, r"Mozilla Firefox\firefox.exe"),
            os.path.join(_PROG86, r"Mozilla Firefox\firefox.exe"),
        ),
        is_chromium=False,
    ),
)


def _resolve(canonical_or_alias: str) -> Optional[_BrowserSpec]:
    if not canonical_or_alias:
        return None
    key = canonical_or_alias.strip().lower()
    for b in _BROWSERS:
        if b.canonical == key or key in b.aliases:
            return b
        for alias in b.aliases:
            if alias in key:
                return b
    return None


def list_known_browsers() -> list[str]:
    return [b.canonical for b in _BROWSERS]


def find_exe(spec: _BrowserSpec) -> Optional[str]:
    """Return absolute path to the browser's executable, or None."""
    for p in spec.fixed_exe_paths:
        if p and os.path.exists(p):
            return p
    on_path = shutil.which(spec.exe_names[0])
    return on_path


# --------------------------------------------------------------------------- #
#  Profile enumeration                                                        #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BrowserProfile:
    directory: str   # e.g. "Default", "Profile 1"
    name: str        # human-friendly name from Local State, fallback to directory


def list_profiles(canonical: str) -> list[BrowserProfile]:
    """Enumerate profiles for a Chromium browser via its Local State file."""
    spec = _resolve(canonical)
    if not spec or not spec.is_chromium:
        return []
    for path in spec.local_state_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.info("[browser] failed to read %s: %s", path, e)
            continue
        info_cache = (data.get("profile") or {}).get("info_cache") or {}
        out: list[BrowserProfile] = []
        for dir_name, meta in info_cache.items():
            friendly = meta.get("name") or meta.get("shortcut_name") or dir_name
            out.append(BrowserProfile(directory=dir_name, name=friendly))
        # Sort so "Default" is first.
        out.sort(key=lambda p: (0 if p.directory == "Default" else 1, p.directory))
        return out
    return []


def profile_for(canonical: str, requested: Optional[str] = None) -> Optional[str]:
    """Resolve a profile name/index to a directory string.

    `requested` can be:
        - None / "" → use settings.default_browser_profile[canonical] if set,
                      otherwise return None (no flag added).
        - "Default" or "Profile 1" → exact directory match.
        - friendly name (e.g. "Shivang Work") → match against profile.name.
        - "1" / "2" → 1-based index into list_profiles().
    """
    profiles = list_profiles(canonical)
    if not profiles:
        return None

    prefs = settings.get("default_browser_profile") or {}
    if not requested:
        saved = prefs.get(canonical)
        if saved:
            return saved
        return None

    req = str(requested).strip()
    low = req.lower()

    for p in profiles:
        if p.directory.lower() == low:
            return p.directory
    for p in profiles:
        if p.name.lower() == low:
            return p.directory
    if low.isdigit():
        idx = int(low) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx].directory
    # Partial match on friendly name.
    for p in profiles:
        if low in p.name.lower():
            return p.directory
    return None


# --------------------------------------------------------------------------- #
#  Foreground / running detection                                             #
# --------------------------------------------------------------------------- #

def _foreground_title() -> str:
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        n = u32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value or ""
    except Exception:
        return ""


_TITLE_HINTS: dict[str, tuple[str, ...]] = {
    "chrome":  ("google chrome",),
    "brave":   ("brave",),
    "edge":    ("microsoft edge", "msedge", "- edge"),
    "firefox": ("firefox", "mozilla firefox"),
    "opera":   (" - opera", "opera browser"),
}


def focused_browser() -> Optional[str]:
    title = _foreground_title().lower()
    if not title:
        return None
    for canonical, hints in _TITLE_HINTS.items():
        for h in hints:
            if h in title:
                return canonical
    return None


def running_browser() -> Optional[str]:
    """Pick any browser that currently has a running process."""
    try:
        import psutil
    except Exception:
        return None
    running = set()
    for proc in psutil.process_iter(["name"]):
        try:
            n = (proc.info["name"] or "").lower()
        except Exception:
            continue
        running.add(n)
    # Prefer the assistant's default if it's running.
    pref = settings.get("default_browser", "system")
    spec = _resolve(pref) if pref and pref != "system" else None
    if spec and any(e.lower() in running for e in spec.exe_names):
        return spec.canonical
    for b in _BROWSERS:
        if any(e.lower() in running for e in b.exe_names):
            return b.canonical
    return None


# --------------------------------------------------------------------------- #
#  Launch                                                                     #
# --------------------------------------------------------------------------- #

@dataclass
class LaunchResult:
    ok: bool
    used_browser: str        # canonical or "system"
    used_profile: Optional[str]
    reason: str              # short human-readable note


def _normalize_url(url_or_query: str, *, is_search: bool = False) -> str:
    u = (url_or_query or "").strip()
    if not u:
        return ""
    if is_search and not u.lower().startswith(("http://", "https://")) and " " in u:
        # plain words -> Google search
        return "https://www.google.com/search?q=" + u.replace(" ", "+")
    if u.lower().startswith(("http://", "https://")):
        return u
    if "." in u and " " not in u:
        return "https://" + u
    if is_search:
        return "https://www.google.com/search?q=" + u.replace(" ", "+")
    return u


def pick_target_browser(requested: Optional[str]) -> tuple[Optional[_BrowserSpec], str]:
    """Returns (spec, reason). spec=None means "fall back to OS default"."""
    if requested:
        s = _resolve(requested)
        if s and find_exe(s):
            return s, f"user-requested {s.canonical}"
        if s:
            return s, f"user-requested {s.canonical} (exe not found; trying anyway)"
    pref = settings.get("default_browser", "system")
    if pref and pref != "system":
        s = _resolve(pref)
        if s and find_exe(s):
            return s, f"default ({s.canonical})"
    foc = focused_browser()
    if foc:
        s = _resolve(foc)
        if s and find_exe(s):
            return s, f"focused window ({s.canonical})"
    run = running_browser()
    if run:
        s = _resolve(run)
        if s and find_exe(s):
            return s, f"running ({s.canonical})"
    return None, "OS default"


def launch(
    url_or_query: str,
    *,
    browser: Optional[str] = None,
    profile: Optional[str] = None,
    is_search: bool = False,
) -> LaunchResult:
    """Open a URL/query in the best browser; honours profile when given."""
    url = _normalize_url(url_or_query, is_search=is_search)
    if not url:
        return LaunchResult(False, "system", None, "empty url")

    spec, reason = pick_target_browser(browser)
    if spec is None:
        try:
            webbrowser.open(url)
            return LaunchResult(True, "system", None, reason)
        except Exception as e:
            return LaunchResult(False, "system", None, f"system default failed: {e}")

    exe = find_exe(spec)
    if not exe:
        try:
            webbrowser.open(url)
            return LaunchResult(True, "system", None,
                                f"{spec.canonical} exe missing, used OS default")
        except Exception as e:
            return LaunchResult(False, spec.canonical, None, f"exe missing and default failed: {e}")

    args: list[str] = [exe]
    profile_dir: Optional[str] = None
    if spec.is_chromium:
        profile_dir = profile_for(spec.canonical, profile)
        if profile_dir:
            args.append(f'--profile-directory={profile_dir}')
    args.append(url)

    try:
        subprocess.Popen(args, close_fds=True)
    except Exception as e:
        log.warning("[browser] launch failed: %s", e)
        try:
            webbrowser.open(url)
            return LaunchResult(True, "system", None,
                                f"{spec.canonical} launch failed: {e}; used default")
        except Exception as e2:
            return LaunchResult(False, spec.canonical, profile_dir,
                                f"both failed: {e2}")
    return LaunchResult(True, spec.canonical, profile_dir, reason)
