#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Channel Finder v4.7.1
  Mode 1 — Search videos (filters, thumbnails, channel stats, download)
  Mode 2 — Download single video by URL (stats + download/thumbnail)
  Mode 3 — Parse channel (long / shorts) + download menu (long/shorts/both + thumbnails)
  Mode 4 — Batch download from videolinks.txt (re-encode to MP4 + metadata)
  Mode 5 — Download thumbnails
  Mode 6 — Playlist Parser (parse playlist → download videos / thumbnails)
"""

import os
import sys
import re
import urllib.parse
import json
import subprocess
import urllib.request
import platform

# ── Cross-platform single-keypress read ──────────────────────────────────────
if platform.system() == 'Windows':
    import msvcrt as _msvcrt

    def _getch() -> bytes:
        """Read one keypress without echoing (Windows)."""
        return _msvcrt.getch()
else:
    import tty
    import termios

    def _getch() -> bytes:
        """Read one keypress without echoing (macOS / Linux)."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            return ch.encode('utf-8', errors='replace')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
import time
import random
import shutil
import atexit
import threading
from datetime import datetime, timedelta

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("google-api-python-client is not installed.")
    print("Run:  pip install google-api-python-client")
    input("Press Enter to exit...")
    sys.exit(1)

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
API_KEYS_FILE = os.path.join(SCRIPT_DIR, 'api_keys.txt')
OUTPUT_FILE   = os.path.join(SCRIPT_DIR, 'find.txt')
THUMBS_DIR    = os.path.join(SCRIPT_DIR, 'thumbnails')
DOWNLOADS_DIR = os.path.join(SCRIPT_DIR, 'downloads')
PARSED_DIR    = os.path.join(SCRIPT_DIR, 'parsed')
VIDEOLINKS    = os.path.join(SCRIPT_DIR, 'videolinks.txt')
COOKIES_FILE  = os.path.join(SCRIPT_DIR, 'cookies.txt')


# ═══════════════════════════════════════════════════════════════════════
#  ENVIRONMENT CHECK
# ═══════════════════════════════════════════════════════════════════════

def ensure_environment():
    """
    Check that all folders and support files required by the script exist.
    Creates anything that is missing and reports what was created.
    Called once on startup, right after the update check.
    """
    created = []
    already_ok = []

    # ── Directories ──────────────────────────────────────────────────────
    required_dirs = [
        (THUMBS_DIR,    'thumbnails/'),
        (DOWNLOADS_DIR, 'downloads/'),
        (PARSED_DIR,    'parsed/'),
    ]
    for path, label in required_dirs:
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(label)
        else:
            already_ok.append(label)

    # ── videolinks.txt — created with a comment template if missing ──────
    if not os.path.isfile(VIDEOLINKS):
        with open(VIDEOLINKS, 'w', encoding='utf-8') as f:
            f.write('# Put one YouTube video URL per line\n')
        created.append('videolinks.txt')
    else:
        already_ok.append('videolinks.txt')

    # ── find.txt — created empty if missing ─────────────────────────────
    if not os.path.isfile(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            pass  # empty file — results are appended by mode_search()
        created.append('find.txt')
    else:
        already_ok.append('find.txt')

    # ── api_keys.txt — critical; create template and warn if missing ─────
    if not os.path.isfile(API_KEYS_FILE):
        with open(API_KEYS_FILE, 'w', encoding='utf-8') as f:
            f.write('# Paste your YouTube Data API v3 key(s) here, one per line\n')
            f.write('# Example:\n')
            f.write('# AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n')
        created.append('api_keys.txt  ← TEMPLATE (add real keys!)')

    # ── Report ────────────────────────────────────────────────────────────
    if created:
        _ui_header('Environment Check', C.CN)
        for item in created:
            _ui_status('◆', item, C.Y)
        if already_ok:
            for item in already_ok:
                _ui_status('✓', item, C.G)
        print()
    # If everything was already in place, stay silent (clean startup)


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

class C:
    """ANSI colour shortcuts."""
    H  = '\033[95m'       # Magenta / Header
    B  = '\033[94m'       # Blue
    CN = '\033[96m'       # Cyan
    G  = '\033[92m'       # Green
    Y  = '\033[93m'       # Yellow
    R  = '\033[91m'       # Red
    BO = '\033[1m'        # Bold
    DM = '\033[2m'        # Dim
    IT = '\033[3m'        # Italic
    UL = '\033[4m'        # Underline
    W  = '\033[97m'       # White (bright)
    DG = '\033[90m'       # Dark gray
    E  = '\033[0m'        # Reset


# ═══════════════════════════════════════════════════════════════════════
#  UI DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _ui_banner(title: str, width: int = 52, color: str = C.H):
    """Print a double-line boxed banner for major sections."""
    inner = width - 4
    pad_text = title.center(inner)
    print(f"{color}{C.BO}")
    print(f"  ╔{'═' * inner}╗")
    print(f"  ║{pad_text}║")
    print(f"  ╚{'═' * inner}╝")
    print(f"{C.E}")


def _ui_header(title: str, color: str = C.CN):
    """Print a section header with decorative line."""
    print(f"\n  {color}{C.BO}{'─' * 3} {title} {'─' * max(1, 40 - len(title))}{C.E}")


def _ui_separator(color: str = C.DG):
    """Print a thin separator line."""
    print(f"  {color}{'─' * 46}{C.E}")


def _ui_menu_item(key: str, label: str, accent: str = C.CN, extra: str = ''):
    """Print a styled menu item with consistent formatting."""
    dot = f"{C.DG}│{C.E}"
    num = f"  {dot} {C.W}{C.BO}{key}.{C.E}"
    ex = f"  {C.DM}{extra}{C.E}" if extra else ''
    print(f"{num} {C.W}{label}{C.E}{ex}")


def _ui_menu_back(key: str = '0', label: str = 'Back'):
    """Print a styled 'Back' / 'Exit' menu item."""
    dot = f"{C.DG}│{C.E}"
    print(f"  {dot} {C.DG}{key}. {label}{C.E}")


def _ui_prompt() -> str:
    """Print a styled input prompt and return user input."""
    return input(f"  {C.CN}›{C.E} ").strip()


def _ui_status(icon: str, message: str, color: str = C.G):
    """Print a status line with icon."""
    print(f"  {color}{icon}{C.E}  {message}")


# ═══════════════════════════════════════════════════════════════════════
#  STARTUP BANNER & ANIMATED LOADING
# ═══════════════════════════════════════════════════════════════════════

def _print_cfinder_banner():
    """Print a large ASCII block-letter CFINDER banner (Gemini CLI style)."""
    # Gradient colors for each row of the banner
    g1 = '\033[38;5;39m'   # bright blue
    g2 = '\033[38;5;38m'   # blue-cyan
    g3 = '\033[38;5;44m'   # cyan
    g4 = '\033[38;5;43m'   # teal
    g5 = '\033[38;5;49m'   # green-cyan
    g6 = '\033[38;5;48m'   # green
    g7 = '\033[38;5;83m'   # bright green
    g8 = '\033[38;5;84m'   # lime
    r  = C.E

    banner_lines = [
        (g1, r"   ██████╗ ███████╗██╗███╗   ██╗██████╗ ███████╗██████╗ "),
        (g2, r"  ██╔════╝ ██╔════╝██║████╗  ██║██╔══██╗██╔════╝██╔══██╗"),
        (g3, r"  ██║      █████╗  ██║██╔██╗ ██║██║  ██║█████╗  ██████╔╝"),
        (g4, r"  ██║      ██╔══╝  ██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗"),
        (g5, r"  ╚██████╗ ██║     ██║██║ ╚████║██████╔╝███████╗██║  ██║"),
        (g6, r"   ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝"),
    ]

    print()
    for color, line in banner_lines:
        print(f"{C.BO}{color}{line}{r}")

    # Tagline under the banner
    print(f"\n        {C.DM}{'─' * 44}{C.E}")
    print(f"         {C.DG}YouTube Channel Finder{C.E}  {C.DM}│{C.E}  {C.W}{C.BO}v4.7.1{C.E}")
    print(f"        {C.DM}{'─' * 44}{C.E}")
    print()


def _spinner_frames():
    """Yield infinite sequence of spinner animation frames."""
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while True:
        yield frames[i % len(frames)]
        i += 1


def _progress_bar_str(progress: float, width: int = 30, filled_color: str = '',
                      empty_color: str = '') -> str:
    """Build a gradient progress bar string. progress is 0.0-1.0."""
    fc = filled_color or '\033[38;5;44m'  # cyan
    ec = empty_color  or C.DG
    filled = int(width * progress)
    empty  = width - filled
    bar = f"{fc}{'━' * filled}{ec}{'─' * empty}{C.E}"
    return bar


def _animated_startup():
    """
    Run the animated startup sequence:
    1. Check / install dependencies with animated progress
    2. Update yt-dlp with spinner
    3. Validate environment
    Shows real-time progress with beautiful graphics.
    """
    # ── Phase 1: Dependency check ────────────────────────────────────
    g_cyan  = '\033[38;5;44m'
    g_green = '\033[38;5;49m'
    g_blue  = '\033[38;5;39m'

    print(f"  {g_blue}{C.BO}⬢{C.E}  {C.W}{C.BO}Installing | updating dependencies...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}\n")

    label_w = max(len(d[2]) for d in _DEPS)
    for spec, dist, label, nightly in _DEPS:
        # Run pip in a worker thread; animate until it finishes
        result = {}

        def _work():
            try:
                result['r'] = _pip_upgrade(spec, dist, nightly)
            except Exception as e:
                result['r'] = ('error', str(e)[:90])

        worker = threading.Thread(target=_work, daemon=True)
        worker.start()
        progress = 0.0
        while worker.is_alive():
            progress += (0.95 - progress) * 0.04        # ease towards 95 %
            bar = _progress_bar_str(progress, 30, g_cyan)
            print(f"\r  {g_cyan}{next(_spinner_gen)}{C.E}  {C.W}{label:<{label_w}}{C.E}  {bar}"
                  f"  {C.DM}{int(progress * 100):3d}%{C.E}  {C.DG}checking{C.E}   ", end='', flush=True)
            time.sleep(0.05)

        state, detail = result['r']
        if state == 'updated':
            status_icon = f"{C.G}{C.BO}✓{C.E}"
            status_msg  = f"{C.G}updated{C.E} {C.DM}({detail}){C.E}"
        elif state == 'ok':
            status_icon = f"{C.G}{C.BO}✓{C.E}"
            status_msg  = f"{C.G}up to date{C.E}" + (f" {C.DM}({detail}){C.E}" if detail else '')
        else:
            status_icon = f"{C.Y}{C.BO}⚠{C.E}"
            status_msg  = f"{C.Y}update failed: {detail}{C.E}"

        bar_done = _progress_bar_str(1.0, 30, g_green if state != 'error' else C.Y)
        print(f"\r  {status_icon}  {C.W}{label:<{label_w}}{C.E}  {bar_done}  {C.DM}100%{C.E}  {status_msg}           ")

    # ── Phase 1b: PO Token server ────────────────────────────────────
    print(f"\n  {g_blue}{C.BO}⬢{C.E}  {C.W}{C.BO}PO Token provider...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}")
    setup_pot_provider()

    # ── Phase 2: Environment check ───────────────────────────────────
    print(f"\n  {g_blue}{C.BO}⬢{C.E}  {C.W}{C.BO}Checking environment...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}")

    env_items = [
        ('thumbnails/',    THUMBS_DIR,    'dir'),
        ('downloads/',     DOWNLOADS_DIR, 'dir'),
        ('parsed/',        PARSED_DIR,    'dir'),
        ('videolinks.txt', VIDEOLINKS,    'file'),
        ('find.txt',       OUTPUT_FILE,   'file'),
        ('api_keys.txt',   API_KEYS_FILE, 'file'),
    ]

    for name, path, kind in env_items:
        # Small animation per item
        for step in range(8):
            spinner = next(_spinner_gen)
            print(f"\r  {g_cyan}{spinner}{C.E}  {C.DM}Scanning {name}...{C.E}    ", end='', flush=True)
            time.sleep(0.015)

        exists = os.path.isdir(path) if kind == 'dir' else os.path.isfile(path)
        created = False

        if not exists:
            if kind == 'dir':
                os.makedirs(path, exist_ok=True)
                created = True
            elif name == 'videolinks.txt':
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('# Put one YouTube video URL per line\n')
                created = True
            elif name == 'find.txt':
                with open(path, 'w', encoding='utf-8') as f:
                    pass
                created = True
            elif name == 'api_keys.txt':
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('# Paste your YouTube Data API v3 key(s) here, one per line\n')
                    f.write('# Example:\n')
                    f.write('# AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n')
                created = True

        if created:
            icon = f"{C.Y}{C.BO}+{C.E}"
            msg  = f"{C.Y}created{C.E}"
        else:
            icon = f"{C.G}✓{C.E}"
            msg  = f"{C.DM}ok{C.E}"
        print(f"\r  {icon}  {C.W}{name:<18}{C.E} {msg}           ")

    # ── Phase 3: Finalize ────────────────────────────────────────────
    print(f"\n  {C.DM}{'─' * 46}{C.E}")
    print(f"  {g_green}{C.BO}✦{C.E}  {C.G}{C.BO}Environment ready!{C.E}")
    print()


# Global spinner generator
_spinner_gen = _spinner_frames()


def safe_filename(name: str) -> str:
    """Remove characters illegal on Windows, keep Unicode letters."""
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.strip('. ')
    return name if name else 'untitled'


def parse_iso_duration(iso: str) -> int:
    """PT1H2M3S → seconds."""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-UPDATE yt-dlp
# ═══════════════════════════════════════════════════════════════════════

# (pip spec, distribution name, label, track nightly builds)
# yt-dlp nightly is what the yt-dlp team recommends for YouTube: fixes for new
# YouTube changes land there days/weeks before a stable release.
# [default] extras bring yt-dlp-ejs (local JS challenge solver), curl_cffi, etc.
_DEPS = [
    ('google-api-python-client',  'google-api-python-client',  'Google API Client', False),
    ('yt-dlp[default]',           'yt-dlp',                    'yt-dlp (nightly)',  True),
    ('bgutil-ytdlp-pot-provider', 'bgutil-ytdlp-pot-provider', 'PO Token plugin',   False),
    ('websocket-client',          'websocket-client',          'websocket-client',  False),
]


def _installed_version(dist: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(dist)
    except Exception:
        return None


def _pip_upgrade(spec: str, dist: str, nightly: bool) -> tuple:
    """Upgrade one package. Returns (state, detail); state = 'updated' | 'ok' | 'error'."""
    before = _installed_version(dist)
    target = spec
    if nightly:
        # Pinning the exact latest pre-release lets pip install it without
        # applying --pre to every dependency.
        r = subprocess.run([sys.executable, '-m', 'pip', 'index', 'versions', dist, '--pre'],
                           capture_output=True, text=True, timeout=60)
        m = re.match(rf'{re.escape(dist)} \(([^)]+)\)', r.stdout.strip())
        if m:
            target = f'{spec}=={m.group(1)}'
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', target],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        lines = [l for l in r.stderr.strip().splitlines() if l.strip()] or ['pip failed']
        return 'error', lines[-1][:90]
    after = _installed_version(dist)
    if after and after != before:
        return 'updated', f'{before or "—"} → {after}'
    return 'ok', after or ''


# ═══════════════════════════════════════════════════════════════════════
#  PO TOKEN PROVIDER (bgutil-ytdlp-pot-provider)
# ═══════════════════════════════════════════════════════════════════════
# The pip plugin asks a local HTTP server for YouTube "Proof of Origin" tokens
# (BotGuard attestation, like a real browser player). The server is built once
# from the repo tag matching the plugin version and started in the background.

_POT_DIR    = os.path.join(SCRIPT_DIR, 'pot-provider')
_POT_SERVER = os.path.join(_POT_DIR, 'server')
_POT_URL    = 'http://127.0.0.1:4416'
_POT_REPO   = 'https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git'
_pot_proc   = None     # server process started by this session (stopped on exit)
_pot_active = False    # True once tokens are available → token-backed clients used


def _pot_ping() -> str | None:
    """Return the running server's version, or None if it is not reachable."""
    try:
        with urllib.request.urlopen(_POT_URL + '/ping', timeout=1.5) as r:
            return json.loads(r.read().decode('utf-8')).get('version')
    except Exception:
        return None


def _pot_built_version() -> str | None:
    if not os.path.isfile(os.path.join(_POT_SERVER, 'build', 'main.js')):
        return None
    try:
        with open(os.path.join(_POT_SERVER, 'package.json'), encoding='utf-8') as f:
            return json.load(f).get('version')
    except Exception:
        return None


def _pot_build(version: str) -> str | None:
    """Clone + build the server for `version`. Returns an error message or None."""
    tools = {t: shutil.which(t) for t in ('git', 'node', 'npm', 'npx')}
    missing = [t for t, p in tools.items() if not p]
    if missing:
        return f"missing {', '.join(missing)} (install Git and Node.js 22+)"
    node_ver = subprocess.run([tools['node'], '--version'], capture_output=True, text=True).stdout
    m = re.match(r'v(\d+)', node_ver.strip())
    if not m or int(m.group(1)) < 22:
        return f'Node.js 22+ required (found {node_ver.strip() or "?"})'
    if os.path.isdir(_POT_DIR):
        try:
            shutil.rmtree(_POT_DIR)
        except Exception as e:
            return f'cannot replace old server (still running?): {e}'
    steps = [
        ([tools['git'], 'clone', '-q', '--depth', '1', '--single-branch',
          '--branch', version, _POT_REPO, _POT_DIR], SCRIPT_DIR),
        ([tools['npm'], 'ci', '--no-audit', '--no-fund'], _POT_SERVER),
        ([tools['npx'], 'tsc'], _POT_SERVER),
    ]
    for cmd, cwd in steps:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            err = [l for l in (r.stderr or r.stdout).strip().splitlines() if l.strip()]
            return f"{os.path.basename(cmd[0])} failed: {(err or ['?'])[-1][:80]}"
    return None


def _pot_stop():
    if _pot_proc is not None and _pot_proc.poll() is None:
        _pot_proc.terminate()


def _pot_start() -> bool:
    global _pot_proc
    log = open(os.path.join(_POT_DIR, 'server.log'), 'w', encoding='utf-8')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    _pot_proc = subprocess.Popen([shutil.which('node'), os.path.join('build', 'main.js')],
                                 cwd=_POT_SERVER, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, creationflags=flags)
    atexit.register(_pot_stop)
    for _ in range(60):
        if _pot_ping():
            return True
        if _pot_proc.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def setup_pot_provider():
    """Startup: make sure the PO-token server matches the plugin and is running.
    On success switch yt-dlp to token-backed clients (mweb + web_safari)."""
    global _pot_active
    plugin = _installed_version('bgutil-ytdlp-pot-provider')
    if not plugin:
        _ui_status('⚠', 'PO Token plugin not installed — using client spoofing only', C.Y)
        return

    running = _pot_ping()
    if running:
        if running != plugin:
            _ui_status('⚠', f'PO Token server v{running} running, plugin is v{plugin} '
                            f'— close the old server (node.exe) and restart', C.Y)
        else:
            _ui_status('✓', f'PO Token server v{running} (already running)', C.G)
    else:
        if _pot_built_version() != plugin:
            print(f"  {C.CN}⟳  Building PO Token server v{plugin} (one-time, ~1 min)...{C.E}",
                  flush=True)
            err = _pot_build(plugin)
            if err:
                _ui_status('⚠', f'PO Token server build failed: {err}', C.Y)
                return
        if not _pot_start():
            _ui_status('⚠', f'PO Token server did not start — see {_POT_DIR}{os.sep}server.log', C.Y)
            return
        _ui_status('✓', f'PO Token server v{plugin} started', C.G)

    _YT_EXTRACTOR_ARGS['youtube']['player_client'] = list(_YT_CLIENTS_POT)
    _pot_active = True


# ═══════════════════════════════════════════════════════════════════════
#  KEY MANAGER
# ═══════════════════════════════════════════════════════════════════════

class KeyManager:
    def __init__(self, path: str):
        self.keys = self._load(path)
        self.idx  = 0
        print(f"  {C.G}{C.BO}✓{C.E}  {C.G}Loaded {len(self.keys)} API key(s){C.E}")

    def _load(self, path: str):
        try:
            # utf-8-sig: Notepad may save with a BOM that would corrupt the first key
            with open(path, 'r', encoding='utf-8-sig') as f:
                keys = [s for s in (line.strip() for line in f)
                        if s and not s.startswith('#')]   # skip template/comment lines
        except FileNotFoundError:
            keys = []
        if not keys:
            print(f"\n  {C.R}{C.BO}✗  No API keys found in {path}{C.E}")
            print(f"  {C.Y}   Add your YouTube Data API v3 key(s) to this file, one per line.{C.E}")
            print(f"  {C.DM}   How to get a key: see \"Getting a YouTube API key\" in README.md{C.E}\n")
            input("  Press Enter to exit...")
            sys.exit(1)
        return keys

    def key(self) -> str:
        return self.keys[self.idx]

    def rotate(self):
        self.idx = (self.idx + 1) % len(self.keys)
        print(f"  {C.Y}⟳  Switched to key #{self.idx + 1}{C.E}")


def check_key_quotas(km: KeyManager):
    """Test each API key with a lightweight call and show status."""
    _ui_header('API Key Status', C.CN)
    first_valid = None
    for i, api_key in enumerate(km.keys):
        try:
            yt = build('youtube', 'v3', developerKey=api_key)
            yt.search().list(part="id", q="test", maxResults=1).execute()
            status = f"{C.G}{C.BO}✓{C.E} {C.G}Active{C.E}"
            if first_valid is None:
                first_valid = i
        except HttpError as e:
            if e.resp.status in (403, 429):
                status = f"{C.R}{C.BO}✗{C.E} {C.R}Quota exhausted{C.E}"
            elif e.resp.status == 400:
                status = f"{C.R}{C.BO}✗{C.E} {C.R}Invalid key{C.E}"
            else:
                status = f"{C.Y}? HTTP {e.resp.status}{C.E}"
        except Exception as e:
            status = f"{C.Y}? Error: {e}{C.E}"
        print(f"  {C.DG}│{C.E} Key #{i+1} {C.DM}(...{api_key[-6:]}){C.E}  {status}")
    
    if first_valid is not None:
        km.idx = first_valid
        print(f"  {C.G}{C.BO}→{C.E} {C.W}Using key #{first_valid + 1} as starting key{C.E}")
    else:
        print(f"  {C.R}{C.BO}⚠{C.E} {C.R}No active keys found! API calls will fail.{C.E}")
    print()


# ═══════════════════════════════════════════════════════════════════════
#  GENERIC API CALL WITH KEY ROTATION
# ═══════════════════════════════════════════════════════════════════════

def api_call(km: KeyManager, build_fn):
    """
    build_fn(youtube_service) → request object.
    Automatically rotates keys on 403/429/400 errors.
    Returns parsed JSON response or None.
    """
    attempts = 0
    while attempts < len(km.keys):
        try:
            yt = build('youtube', 'v3', developerKey=km.key())
            return build_fn(yt).execute()
        except HttpError as e:
            code = e.resp.status
            if code in (403, 429, 400):
                print(f"  {C.R}✗  Key ...{km.key()[-6:]} error {code}. Rotating...{C.E}")
                km.rotate()
                attempts += 1
            else:
                print(f"  {C.R}✗  HTTP {code}: {e}{C.E}")
                return None
        except Exception as e:
            print(f"  {C.R}✗  Error: {e}{C.E}")
            return None
    print(f"  {C.R}✗  All API keys exhausted.{C.E}")
    return None


# ═══════════════════════════════════════════════════════════════════════
#  MODE 1 — SEARCH
# ═══════════════════════════════════════════════════════════════════════

def ask_filters() -> dict:
    """Prompt user for advanced search filters."""
    _ui_header('Filters', C.B)
    print(f"  {C.DM}Press Enter to skip any filter{C.E}\n")

    print(f"  {C.B}{C.BO}Duration:{C.E}")
    print(f"  {C.DG}│{C.E} {C.W}1{C.E} = any   {C.W}2{C.E} = short (<4m)   {C.W}3{C.E} = medium (4-20m)   {C.W}4{C.E} = long (>20m)")
    d = input(f"  {C.CN}›{C.E} ").strip()
    duration = {'2': 'short', '3': 'medium', '4': 'long'}.get(d, 'any')

    print(f"  {C.B}{C.BO}Quality:{C.E}")
    print(f"  {C.DG}│{C.E} {C.W}1{C.E} = any   {C.W}2{C.E} = SD   {C.W}3{C.E} = HD")
    df = input(f"  {C.CN}›{C.E} ").strip()
    definition = {'2': 'standard', '3': 'high'}.get(df, 'any')

    print(f"  {C.B}{C.BO}Date range:{C.E}")
    print(f"  {C.DG}│{C.E} {C.W}1{C.E} = any  {C.W}2{C.E} = hour  {C.W}3{C.E} = today  {C.W}4{C.E} = week  {C.W}5{C.E} = month  {C.W}6{C.E} = year")
    ud = input(f"  {C.CN}›{C.E} ").strip()
    now = datetime.utcnow()
    pub_after = None
    deltas = {
        '2': timedelta(hours=1),
        '3': timedelta(hours=now.hour, minutes=now.minute),
        '4': timedelta(days=7),
        '5': timedelta(days=30),
        '6': timedelta(days=365),
    }
    if ud in deltas:
        pub_after = (now - deltas[ud]).strftime('%Y-%m-%dT%H:%M:%SZ')

    lang = input(f"  {C.B}{C.BO}Language{C.E} {C.DM}(ru/en/uk/ja/ar/...){C.E}: ").strip() or None

    ps = input(f"  {C.B}{C.BO}Results per page{C.E} {C.DM}[25]{C.E}: ").strip()
    try:
        page_size = min(max(int(ps), 1), 50)
    except ValueError:
        page_size = 25

    return dict(duration=duration, definition=definition,
                published_after=pub_after, language=lang, page_size=page_size)


def search_youtube_all(km: KeyManager, query: str, filters: dict) -> list:
    """Fetch ALL YouTube search results using nextPageToken pagination."""
    all_items = []
    page_token = None
    total_reported = None

    while True:
        def req(yt, pt=page_token):
            params = dict(part="snippet", maxResults=50,
                          q=query, type="video")
            if filters['duration'] != 'any':
                params['videoDuration'] = filters['duration']
            if filters['definition'] != 'any':
                params['videoDefinition'] = filters['definition']
            if filters['published_after']:
                params['publishedAfter'] = filters['published_after']
            if filters['language']:
                params['relevanceLanguage'] = filters['language']
            if pt:
                params['pageToken'] = pt
            return yt.search().list(**params)

        resp = api_call(km, req)
        if not resp:
            break

        if total_reported is None:
            total_reported = resp.get('pageInfo', {}).get('totalResults', '?')
            print(f"  {C.CN}API reports ~{total_reported} total result(s){C.E}")

        items = resp.get('items', [])
        all_items.extend(items)

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

        print(f"  {C.DM}⟳  Fetched {len(all_items)} so far...{C.E}")

    return all_items


def get_channel_stats(km: KeyManager, channel_ids: list) -> dict:
    """Fetch channel statistics for a list of IDs."""
    if not channel_ids:
        return {}
    resp = api_call(km, lambda yt: yt.channels().list(
        part="snippet,statistics", id=','.join(channel_ids[:50])))
    if not resp:
        return {}
    out = {}
    for it in resp.get('items', []):
        s = it.get('statistics', {})
        out[it['id']] = dict(
            title=it['snippet']['title'],
            subs=s.get('subscriberCount', '?'),
            vids=s.get('videoCount', '?'),
            views=s.get('viewCount', '?'),
        )
    return out


def _print_result_item(i: int, it: dict, ch_stats: dict):
    """Print a single search result item."""
    vid = it['id'].get('videoId')
    if not vid:
        return
    sn = it['snippet']
    cid = sn.get('channelId', '')
    print(f"  {C.BO}{i}.{C.E} {C.CN}{sn['title']}{C.E}")
    print(f"     {C.B}https://www.youtube.com/watch?v={vid}{C.E}")
    print(f"     Channel: {sn.get('channelTitle', '?')}  |  {sn.get('publishedAt', '')[:10]}")
    cs = ch_stats.get(cid)
    if cs:
        print(f"     {C.Y}Subs: {cs['subs']}  Videos: {cs['vids']}  Views: {cs['views']}{C.E}")
    print()


def display_results_paginated(results: list, ch_stats: dict, page_size: int = 25):
    """Display search results with paginated output.
    Space = next page, Escape = stop and return to actions menu."""
    if not results:
        print(f"  {C.Y}No results found.{C.E}")
        return

    total = len(results)
    total_pages = (total + page_size - 1) // page_size
    current_page = 0

    _ui_separator()
    print(f"  {C.G}{C.BO}Found {total} video(s).{C.E}  {C.DM}{total_pages} page(s) · {page_size}/page{C.E}")
    print(f"  {C.DM}[Space] = next page  │  [Escape] = actions menu{C.E}")
    _ui_separator()
    print()

    while current_page < total_pages:
        start = current_page * page_size
        end = min(start + page_size, total)

        for i in range(start, end):
            _print_result_item(i + 1, results[i], ch_stats)

        current_page += 1

        if current_page < total_pages:
            shown = end
            remaining = total - shown
            _ui_separator()
            print(f"  {C.DM}Shown {shown}/{total}  │  Remaining: {remaining}  │  "
                  f"Page {current_page}/{total_pages}{C.E}")
            print(f"  {C.DM}[Space] next {min(page_size, remaining)}  │  [Escape] stop{C.E}")
            _ui_separator()
            print()

            # Wait for keypress
            while True:
                key = _getch()
                if key == b' ':     # Space
                    break
                elif key == b'\x1b':  # Escape
                    print(f"\n  {C.CN}Stopped. Shown {shown} of {total} results.{C.E}")
                    return
                # ignore other keys
        else:
            _ui_separator()
            print(f"  {C.G}{C.BO}✓{C.E}  {C.G}All {total} result(s) displayed{C.E}")
            _ui_separator()


def download_thumbnails_search(results: list):
    """Download max-res thumbnails named by video title."""
    os.makedirs(THUMBS_DIR, exist_ok=True)
    count = 0
    for it in results:
        vid = it['id'].get('videoId')
        if not vid:
            continue
        title = safe_filename(it['snippet']['title'])
        # maxresdefault gives highest quality; fallback to hqdefault
        fname = os.path.join(THUMBS_DIR, f"{title} [{vid}].jpg")
        url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
        try:
            urllib.request.urlretrieve(url, fname)
            if os.path.getsize(fname) < 5000:
                url = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                urllib.request.urlretrieve(url, fname)
            count += 1
            print(f"  {C.G}✓{C.E}  {title}")
        except Exception as e:
            print(f"  {C.R}✗  {vid}: {e}{C.E}")
    _ui_separator()
    print(f"  {C.G}{C.BO}✦{C.E}  {C.G}Downloaded {count} thumbnail(s) → {THUMBS_DIR}{C.E}")
    _ui_separator()


def save_results(results: list, query: str):
    """Append ALL search results to find.txt — URLs only, one per line."""
    count = 0
    try:
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n--- [{datetime.now().strftime('%Y-%m-%d %H:%M')}] {query} ---\n")
            for it in results:
                vid = it['id'].get('videoId')
                if vid:
                    f.write(f"https://www.youtube.com/watch?v={vid}\n")
                    count += 1
        print(f"  {C.G}✓{C.E}  {C.G}Saved {count} link(s) → {OUTPUT_FILE}{C.E}")
    except Exception as e:
        print(f"  {C.R}✗  Save error: {e}{C.E}")


def _pick_quality() -> dict:
    """Ask user for download quality. Returns yt-dlp opts fragment."""
    _ui_header('Download Quality', C.G)
    _ui_menu_item('1', '1080p', C.G, 'MP4')
    _ui_menu_item('2', '720p', C.CN, 'MP4')
    _ui_menu_item('3', '480p', C.CN, 'MP4')
    _ui_menu_item('4', 'Audio only', C.Y, 'MP3 192kbps')
    _ui_menu_item('5', 'Ultra High', C.H, '4K | 8K')
    q = _ui_prompt()

    opts = {}
    if q == '2':
        opts['format'] = ('bestvideo[height<=720]+bestaudio'
                          '/bestvideo*[height<=720]+bestaudio'
                          '/best[height<=720]/best/worst')
    elif q == '3':
        opts['format'] = ('bestvideo[height<=480]+bestaudio'
                          '/bestvideo*[height<=480]+bestaudio'
                          '/best[height<=480]/best/worst')
    elif q == '4':
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    elif q == '5':
        # Sentinel — actual format resolved per-URL after probing
        opts['_quality_mode'] = 'ultra_high'
    else:
        # 1080p cap with full fallback chain
        opts['format'] = ('bestvideo[height<=1080]+bestaudio'
                          '/bestvideo*[height<=1080]+bestaudio'
                          '/best[height<=1080]/best/worst')

    # For video modes (not audio-only and not ultra_high sentinel), add MP4 postprocessor
    if q not in ('4', '5'):
        opts['merge_output_format'] = 'mp4'
        opts['postprocessors'] = opts.get('postprocessors', []) + [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]

    return opts


# Extractor args for yt-dlp to bypass YouTube BotGuard/PO-token blocks without cookies.
# VisionOS and Safari clients do not require web BotGuard challenge attestation
# and return full streams (including 1080p, 4K UHD).
# 'web' is intentionally omitted: it only yields SABR formats (not downloadable)
# and each extra client = one more player request counted by YouTube's rate limiter.
_YT_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['visionos', 'web_safari'],
    }
}
# Used instead when the PO Token server is running (setup_pot_provider()):
# mweb + PO token is the setup recommended by yt-dlp; both clients get real
# BotGuard tokens and look like ordinary browser players.
_YT_CLIENTS_POT = ['mweb', 'web_safari']


def _probe_uhd_formats(url: str, cookie_opts: dict) -> tuple:
    """Return (heights, raw_info): descending heights >=2160 and the unprocessed info dict.

    raw_info is reused by _download_one() so the video is not extracted twice.
    Bot/rate-limit errors are re-raised so the caller can stop the batch.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return [], None
    probe_opts = {
        'quiet': True,
        'no_warnings': True,
        'logger': _YtLogger(),
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
        'extractor_args': _YT_EXTRACTOR_ARGS,
    }
    for k, v in cookie_opts.items():
        if not k.startswith('_'):
            probe_opts[k] = v
    try:
        with YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False, process=False)
        if not info:
            return [], None
        seen, result = set(), []
        for f in info.get('formats', []):
            h = f.get('height') or 0
            if h >= 2160 and h not in seen:
                seen.add(h)
                result.append(h)
        return sorted(result, reverse=True), info
    except Exception as e:
        if _is_bot_error(str(e)):
            raise
        return [], None


def _pick_uhd_resolution(available: list) -> str:
    """Show available UHD resolutions, return yt-dlp format string or '' to go back."""
    print(f"\n  {C.G}{C.BO}Available Ultra HD resolutions:{C.E}")
    for i, h in enumerate(available, 1):
        label = '8K' if h >= 4320 else '4K'
        _ui_menu_item(str(i), f"{h}p", C.H, label)
    _ui_menu_back('0', 'Back to quality menu')
    ch = _ui_prompt()
    if ch == '0':
        return ''
    try:
        h = available[int(ch) - 1]
        return (f'bestvideo[height<={h}]+bestaudio'
                f'/bestvideo*[height<={h}]+bestaudio'
                f'/best[height<={h}]/best/worst')
    except (ValueError, IndexError):
        return ''


# ── Cookie file candidates (in order of priority) ──────────────────────
_COOKIE_CANDIDATES = ['cookies.txt', 'www.youtube.com_cookies.txt', 'youtube_cookies.txt']

# Lightweight public video used to validate cookies (Rick Astley – Never Gonna Give You Up)
_COOKIE_TEST_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


def _validate_cookie_file(cfile: str) -> bool:
    """
    Try a lightweight yt-dlp extract_info (no download) with the given cookies.txt.
    Returns True if cookies appear valid, False otherwise.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return True  # can't validate, assume ok

    print(f"  {C.CN}Validating cookies...{C.E}", end='', flush=True)
    opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cfile,
        'logger': _YtLogger(),
        'skip_download': True,
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
        'extractor_args': _YT_EXTRACTOR_ARGS,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(_COOKIE_TEST_URL, download=False, process=False)
        if info and info.get('id'):
            print(f" {C.G}OK ✓{C.E}")
            return True
        print(f" {C.R}FAILED ✗{C.E}")
        return False
    except Exception as e:
        msg = str(e).lower()
        if any(s in msg for s in ('sign in', 'not a bot', '429', 'confirm')):
            print(f" {C.R}FAILED ✗  (cookies rejected by YouTube){C.E}")
        else:
            print(f" {C.R}FAILED ✗  ({e}){C.E}")
        return False


def _fresh_cookie_opts() -> dict | None:
    """Export fresh cookies from the dedicated browser profile (cookie_extractor.py)
    into cookies.txt, validate them and return yt-dlp cookie opts, or None."""
    try:
        import cookie_extractor
    except ImportError as e:
        print(f"  {C.R}✗  cookie_extractor.py not available: {e}{C.E}")
        return None
    if not cookie_extractor.ensure_cookies(COOKIES_FILE):
        print(f"  {C.Y}  Run extract_cookies.cmd to set up / sign in, then try again.{C.E}")
        return None
    if not _validate_cookie_file(COOKIES_FILE):
        return None
    return {'cookiefile': COOKIES_FILE, '_cookie_mode': 'file'}


def _scan_dir_for_cookies(directory: str) -> str | None:
    """Scan a directory for a Netscape cookies file. Returns path or None."""
    for name in _COOKIE_CANDIDATES:
        p = os.path.join(directory, name)
        if os.path.isfile(p):
            return p
    return None


def _pick_cookie_source() -> dict:
    """
    Ask the user how to handle cookies.
    Returns a dict of yt-dlp options to merge, plus a special key
    '_cookie_mode' = 'none' | 'file' for retry logic.
    """
    _ui_header('Cookies | Authentication', C.Y)
    bypass = 'PO tokens + mweb/Safari clients' if _pot_active else 'VisionOS/Safari client bypass'
    _ui_menu_item('1', 'No cookies', C.G, bypass)
    _ui_menu_item('2', 'Fresh cookies from tool browser profile', C.CN, '← recommended if blocked')
    print(f"      {C.DM}Auto-exports a signed-in session to cookies.txt (same as extract_cookies.cmd){C.E}")
    _ui_menu_item('3', 'Use cookies from a .txt file', C.G, '← for private/age-gated videos')
    ch = _ui_prompt()

    if ch == '2':
        return _fresh_cookie_opts() or {'_cookie_mode': 'none'}

    if ch == '3':
        # ── Option 3: cookies.txt file ─────────────────────────────────
        print(f"\n  {C.CN}{C.BO}Cookie file selection:{C.E}")
        print(f"  {C.DG}│{C.E} {C.W}[Enter]{C.E} — scan current folder for cookies.txt")
        print(f"  {C.DG}│{C.E} {C.W}[Path] {C.E} — type custom path to file or folder")
        raw = input(f"  {C.CN}›{C.E} ").strip().strip('"')

        if not raw:
            # Auto-scan the folder where the script lives
            found = _scan_dir_for_cookies(SCRIPT_DIR)
            if found:
                print(f"  {C.G}Found: {found}{C.E}")
                cfile = found
            else:
                print(f"  {C.R}No cookies file found in: {SCRIPT_DIR}{C.E}")
                print(f"  {C.Y}  Expected one of: {', '.join(_COOKIE_CANDIDATES)}{C.E}")
                return {'_cookie_mode': 'none'}
        elif os.path.isdir(raw):
            # User gave a directory — scan it
            found = _scan_dir_for_cookies(raw)
            if found:
                print(f"  {C.G}Found: {found}{C.E}")
                cfile = found
            else:
                print(f"  {C.R}No cookies file found in: {raw}{C.E}")
                print(f"  {C.Y}  Expected one of: {', '.join(_COOKIE_CANDIDATES)}{C.E}")
                return {'_cookie_mode': 'none'}
        elif os.path.isfile(raw):
            cfile = raw
        else:
            print(f"  {C.R}Not found: {raw}{C.E}")
            return {'_cookie_mode': 'none'}

        # ── Validate cookies before proceeding ─────────────────────────
        if not _validate_cookie_file(cfile):
            print(f"  {C.R}Cookie validation failed — cookies are expired or invalid.{C.E}")
            print(f"  {C.Y}  Re-export cookies from your browser and try again.{C.E}")
            return {'_cookie_mode': 'none'}

        print(f"  {C.G}Will use cookies from: {cfile}{C.E}")
        return {'cookiefile': cfile, '_cookie_mode': 'file'}

    return {'_cookie_mode': 'none'}


_BOT_SIGNALS = [
    'sign in to confirm',
    'not a bot',
    'cookies',
    '429',
    'too many requests',
    'nsig extraction failed',
    'try again later',        # "This content isn't available, try again later" = rate limit
    'rate-limit',
    'rate limit',
]


def _save_video_metadata(info_dict: dict, out_dir: str):
    """Save all available metadata of a video to a .txt file in out_dir."""
    if not info_dict:
        return
    title = safe_filename(info_dict.get('title', 'untitled'))
    vid = info_dict.get('id', 'unknown')
    meta_path = os.path.join(out_dir, f"{title} [{vid}].txt")
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            f.write(f"Title: {info_dict.get('title', '')}\n")
            f.write(f"ID: {vid}\n")
            f.write(f"URL: {info_dict.get('webpage_url', '')}\n")
            f.write(f"Channel: {info_dict.get('channel', info_dict.get('uploader', ''))}\n")
            f.write(f"Channel URL: {info_dict.get('channel_url', info_dict.get('uploader_url', ''))}\n")
            f.write(f"Upload Date: {info_dict.get('upload_date', '')}\n")
            f.write(f"Duration: {info_dict.get('duration_string', info_dict.get('duration', ''))}\n")
            f.write(f"View Count: {info_dict.get('view_count', '')}\n")
            f.write(f"Like Count: {info_dict.get('like_count', '')}\n")
            f.write(f"Comment Count: {info_dict.get('comment_count', '')}\n")
            f.write(f"Resolution: {info_dict.get('resolution', '')}\n")
            f.write(f"FPS: {info_dict.get('fps', '')}\n")
            f.write(f"File Size (approx): {info_dict.get('filesize_approx', '')}\n")
            f.write(f"Categories: {', '.join(info_dict.get('categories', []))}\n")
            f.write(f"Tags: {', '.join(info_dict.get('tags', []))}\n")
            desc = info_dict.get('description', '')
            f.write(f"\n─── Description ───\n{desc}\n")
        meta_fname = os.path.basename(meta_path)
        print(f"  {C.G}✓{C.E}  {C.DM}Meta  {C.E}{C.DG}{meta_fname}{C.E}")
    except Exception as e:
        print(f"  {C.R}Failed to save metadata: {e}{C.E}")


class _YtLogger:
    """Custom logger for yt-dlp: suppresses noise, shows errors and important warnings."""
    _IMPORTANT_WARNINGS = [
        'cookies are no longer valid',
        'cookies have likely been rotated',
        'sign in',
    ]

    def debug(self, msg):
        pass  # suppress verbose debug output

    def info(self, msg):
        pass

    def warning(self, msg):
        ml = msg.lower()
        # Only show warnings that the user actually needs to act on
        if any(s in ml for s in self._IMPORTANT_WARNINGS):
            print(f"  {C.Y}⚠  {msg}{C.E}")

    def error(self, msg):
        print(f"{C.R}  ERROR: {msg}{C.E}")



# ── Download phase tracker ──────────────────────────────────────────────
# Tracks which stream (video/audio) is currently being downloaded.
# yt-dlp downloads video and audio separately; we detect the type from
# the info_dict fields and render a labelled progress line for each.
_dl_phase = {
    'stream_index': 0,       # 0 = first stream (video), 1 = second (audio)
    'last_was_finished': False,
    'video_done': False,
    'audio_done': False,
    'merge_done': False,
    'pp_done': set(),          # tracks which pp phases already displayed 'finished'
}

def _dl_phase_reset():
    """Reset download phase tracker before each URL."""
    _dl_phase['stream_index'] = 0
    _dl_phase['last_was_finished'] = False
    _dl_phase['video_done'] = False
    _dl_phase['audio_done'] = False
    _dl_phase['merge_done'] = False
    _dl_phase['pp_done'] = set()


def _detect_stream_type(d: dict) -> str:
    """Detect whether the current yt-dlp download fragment is video or audio."""
    info = d.get('info_dict', {})
    # yt-dlp sets 'vcodec' / 'acodec' on individual format fragments
    vcodec = info.get('vcodec', 'none') or 'none'
    acodec = info.get('acodec', 'none') or 'none'
    has_video = vcodec != 'none'
    has_audio = acodec != 'none'
    # If it has video (with or without audio) → video stream
    if has_video:
        return 'video'
    # Pure audio stream
    if has_audio:
        return 'audio'
    # Fallback: use stream_index (first = video, second = audio)
    return 'video' if _dl_phase['stream_index'] == 0 else 'audio'


# ── Phase display config ────────────────────────────────────────────────
_PHASE_CFG = {
    'video': {
        'icon': '►',
        'label': 'Video',
        'label_done': 'Video',
        'label_color': C.H,          # magenta
        'bar_color': '\033[38;5;40m', # bright green
        'done_color': C.G,
    },
    'audio': {
        'icon': '♫',
        'label': 'Audio',
        'label_done': 'Audio',
        'label_color': C.CN,          # cyan
        'bar_color': '\033[38;5;39m', # bright blue/cyan
        'done_color': '\033[38;5;39m',
    },
    'merge': {
        'icon': '⊕',
        'label': 'Merging',
        'label_done': 'Merged',
        'label_color': C.Y,           # yellow
        'bar_color': '\033[38;5;40m', # green
        'done_color': C.G,
    },
    'convert': {
        'icon': '⊛',
        'label': 'Converting',
        'label_done': 'Converted',
        'label_color': C.W,           # white
        'bar_color': '\033[38;5;44m', # cyan-teal
        'done_color': '\033[38;5;44m',
    },
    'extract': {
        'icon': '♪',
        'label': 'Extracting',
        'label_done': 'Extracted',
        'label_color': C.H,           # magenta
        'bar_color': '\033[38;5;201m', # magenta-pink
        'done_color': '\033[38;5;201m',
    },
}


# ── Label alignment ─────────────────────────────────────────────────────
_LABEL_WIDTH = 10   # Longest label: "Converting" / "Extracting" = 10 chars

# ── Postprocessor animation ─────────────────────────────────────────────
# Background thread that animates the progress bar while FFmpeg processes.
# yt-dlp only fires 'started' and 'finished' — no intermediate progress —
# so we simulate a smooth fill from 0→95% and snap to 100% on completion.

_pp_anim = {
    'stop_event': None,   # threading.Event — set to stop animation
    'thread': None,       # animation thread reference
}


def _pp_animate(cfg: dict, bar_width: int, stop_event: threading.Event):
    """Background animation loop for post-processing phases."""
    progress = 0.0
    # Ease-out: fast at start, slows towards 95%
    while not stop_event.is_set() and progress < 0.95:
        spinner = next(_spinner_gen)
        bar = _progress_bar_str(progress, bar_width, cfg['bar_color'], C.DG)
        pct_str = f"{progress * 100:5.1f}%"
        padded = cfg['label'].ljust(_LABEL_WIDTH)
        print(f"\r  {cfg['bar_color']}{spinner}{C.E}  "
              f"{cfg['label_color']}{cfg['icon']} {padded}{C.E}  "
              f"{bar}  {C.DM}{pct_str}{C.E}   ",
              end='', flush=True)
        # Ease-out increment: slows as we approach 95%
        remaining = 0.95 - progress
        progress += remaining * 0.08
        stop_event.wait(0.1)  # ~10 FPS, exits immediately if stop_event is set


def _format_eta(seconds) -> str:
    """Format ETA seconds into mm:ss or hh:mm:ss string."""
    if seconds is None or seconds < 0:
        return '?'
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def _progress_hook(d):
    """Styled, labelled progress bar for yt-dlp downloads.

    Shows per-stream lines with percent, speed, and ETA:
      ⠹  ► Video  ━━━━━━━━━━━━────────  62.5%  12.3 MB/s  ETA 00:04
      ✓  ► Video  ━━━━━━━━━━━━━━━━━━━━  100%
      ⠹  ♫ Audio  ━━━━━━━━────────────  45.0%   5.1 MB/s  ETA 00:02
      ✓  ♫ Audio  ━━━━━━━━━━━━━━━━━━━━  100%
    """
    stream_type = _detect_stream_type(d)
    cfg = _PHASE_CFG.get(stream_type, _PHASE_CFG['video'])
    bar_width = 28

    if d['status'] == 'downloading':
        _dl_phase['last_was_finished'] = False
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed')
        eta = d.get('eta')
        pct = (downloaded / total) if total > 0 else 0.0

        bar = _progress_bar_str(pct, bar_width, cfg['bar_color'], C.DG)
        spinner = next(_spinner_gen)
        pct_str = f"{pct * 100:5.1f}%"
        speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ''
        eta_str = f"ETA {_format_eta(eta)}" if eta else ''

        padded = cfg['label'].ljust(_LABEL_WIDTH)
        print(f"\r  {cfg['bar_color']}{spinner}{C.E}  "
              f"{cfg['label_color']}{cfg['icon']} {padded}{C.E}  "
              f"{bar}  {C.DM}{pct_str}{C.E}  "
              f"{C.DG}{speed_str}  {eta_str}{C.E}   ",
              end='', flush=True)

    elif d['status'] == 'finished':
        bar_done = _progress_bar_str(1.0, bar_width, cfg['done_color'])
        padded = cfg.get('label_done', cfg['label']).ljust(_LABEL_WIDTH)
        print(f"\r  {C.G}{C.BO}✓{C.E}  "
              f"{cfg['label_color']}{cfg['icon']} {padded}{C.E}  "
              f"{bar_done}  {C.G}100%{C.E}                              ")
        # Mark phase as done and advance stream index
        _dl_phase[f'{stream_type}_done'] = True
        _dl_phase['stream_index'] += 1
        _dl_phase['last_was_finished'] = True


def _postprocessor_hook(d):
    """Animated post-processing progress with real-time bar movement.

    On 'started': spawns background thread animating progress 0→95%
      ⠹  ⚙Converting  ━━━━━━━━━━━━━━──────────────  52.3%
    On 'finished': stops animation, overwrites with done state
      ✓  ⚙Converted   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  100%
    """
    bar_width = 28

    def _resolve_pp_phase(pp: str) -> str | None:
        if 'Merger' in pp:
            return 'merge'
        if 'VideoConvertor' in pp or 'VideoRemuxer' in pp:
            return 'convert'
        if 'ExtractAudio' in pp or 'FFmpegExtractAudio' in pp:
            return 'extract'
        return None

    pp = d.get('postprocessor', '')
    phase = _resolve_pp_phase(pp)
    if phase is None:
        return

    cfg = _PHASE_CFG[phase]

    if d['status'] == 'started':
        # Skip if this phase already completed (e.g. VideoRemuxer + VideoConvertor)
        if phase in _dl_phase['pp_done']:
            return
        # Stop any previous animation
        if _pp_anim['stop_event'] is not None:
            _pp_anim['stop_event'].set()
            if _pp_anim['thread'] and _pp_anim['thread'].is_alive():
                _pp_anim['thread'].join(timeout=1)
        # Start new animation thread
        stop_evt = threading.Event()
        _pp_anim['stop_event'] = stop_evt
        t = threading.Thread(target=_pp_animate, args=(cfg, bar_width, stop_evt),
                             daemon=True)
        _pp_anim['thread'] = t
        t.start()

    elif d['status'] == 'finished':
        # Skip if this phase already completed
        if phase in _dl_phase['pp_done']:
            # Still stop any running animation
            if _pp_anim['stop_event'] is not None:
                _pp_anim['stop_event'].set()
            return
        # Stop animation thread
        if _pp_anim['stop_event'] is not None:
            _pp_anim['stop_event'].set()
            if _pp_anim['thread'] and _pp_anim['thread'].is_alive():
                _pp_anim['thread'].join(timeout=2)
            _pp_anim['stop_event'] = None
            _pp_anim['thread'] = None
        # Overwrite with done state (label changes: Converting→Converted etc.)
        label_done = cfg.get('label_done', cfg['label'])
        bar_done = _progress_bar_str(1.0, bar_width, cfg['done_color'])
        padded = label_done.ljust(_LABEL_WIDTH)
        print(f"\r  {C.G}{C.BO}✓{C.E}  "
              f"{cfg['label_color']}{cfg['icon']} {padded}{C.E}  "
              f"{bar_done}  {C.G}100%{C.E}                              ")
        _dl_phase['pp_done'].add(phase)


def _is_bot_error(msg: str) -> bool:
    """Return True if the error message looks like a bot/auth block."""
    msg_lower = msg.lower()
    return any(sig in msg_lower for sig in _BOT_SIGNALS)


def _build_ydl_opts(out_dir: str, quality_opts: dict, cookie_opts: dict) -> dict:
    """Assemble the full yt-dlp options dict."""
    template = os.path.join(out_dir, '%(title)s [%(id)s].%(ext)s')
    opts = {
        'outtmpl':          template,
        'ignoreerrors':     False,    # we handle errors ourselves for retry logic
        'encoding':         'utf-8',
        'windowsfilenames': True,
        'restrictfilenames': False,
        'quiet':            True,
        'no_warnings':      True,     # suppress stderr; _YtLogger filters selectively
        'noprogress':       True,
        'logger':           _YtLogger(),
        'progress_hooks':   [_progress_hook],
        'postprocessor_hooks': [_postprocessor_hook],
        # Use Node.js for JS extraction (yt-dlp expects dict format: {runtime: {config}})
        'js_runtimes':      {'node': {}},
        # Download EJS challenge solver from GitHub (required to decrypt YouTube stream URLs)
        'remote_components': ['ejs:github'],
        # Spoof VisionOS & Safari clients to bypass YouTube BotGuard checks without cookies
        'extractor_args':   _YT_EXTRACTOR_ARGS,
        # Pace requests inside one extraction (webpage → player → ...) like a browser would
        'sleep_interval_requests': 1,
        # Back off exponentially on HTTP/fragment errors instead of hammering YouTube
        'retry_sleep_functions': {
            'http':      lambda n: min(2 ** n, 30),
            'fragment':  lambda n: min(2 ** n, 30),
            'extractor': lambda n: min(5 * (n + 1), 30),
        },
    }
    opts.update(quality_opts)
    # Apply cookie options (strip our internal meta keys)
    for k, v in cookie_opts.items():
        if not k.startswith('_'):
            opts[k] = v
    return opts


def _remove_url_from_videolinks(url: str):
    """
    Remove a single URL from videolinks.txt after a successful download.
    Preserves all other lines (including comment lines starting with #).
    """
    if not os.path.isfile(VIDEOLINKS):
        return
    try:
        with open(VIDEOLINKS, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = [l for l in lines if l.strip() != url]
        if len(new_lines) != len(lines):  # only write if something changed
            with open(VIDEOLINKS, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
    except Exception as e:
        print(f"  {C.Y}⚠  Could not update videolinks.txt: {e}{C.E}")


# ── Anti-bot pacing ─────────────────────────────────────────────────────
# YouTube guest sessions are rate-limited to ~300 videos/hour (~1000 player
# requests/hour). Random human-like pauses + a periodic long break keep long
# batches well below that limit.
_PAUSE_MIN, _PAUSE_MAX           = 6.0, 14.0     # seconds between videos
_LONG_BREAK_EVERY                = 25            # videos
_LONG_BREAK_MIN, _LONG_BREAK_MAX = 90.0, 180.0   # seconds


def _polite_pause(done: int):
    """Random pause between downloads; a longer break every _LONG_BREAK_EVERY videos."""
    if done % _LONG_BREAK_EVERY == 0:
        secs  = random.uniform(_LONG_BREAK_MIN, _LONG_BREAK_MAX)
        label = 'Long break (staying under YouTube rate limit)'
    else:
        secs  = random.uniform(_PAUSE_MIN, _PAUSE_MAX)
        label = 'Pause'
    end = time.time() + secs
    while True:
        left = end - time.time()
        if left <= 0:
            break
        print(f"\r  {C.DM}⏸  {label}: {left:4.0f}s{C.E}   ", end='', flush=True)
        time.sleep(min(1.0, left))
    print('\r' + ' ' * 70 + '\r', end='', flush=True)


def _print_bot_block_help(remaining: int, from_videolinks: bool):
    """Explain a bot/rate-limit block after the batch has been stopped."""
    print(f"\n  {C.Y}⚠  YouTube flagged this session — batch stopped so the block doesn't get worse.{C.E}")
    print(f"  {C.DM}   Wait 30–60 min before resuming, or switch cookie mode (browser / cookies.txt).{C.E}")
    if from_videolinks:
        print(f"  {C.DM}   {remaining} URL(s) not downloaded remain in videolinks.txt — resume via Mode 4.{C.E}")


def _download_one(ydl, url: str, i: int, total: int, out_dir: str,
                  from_videolinks: bool = False, raw: dict = None) -> bool:
    """Download a single URL. Returns True on success, False on failure.

    When from_videolinks=True the URL will be removed from videolinks.txt
    after a successful download.
    raw — already-extracted (process=False) info dict to reuse; skips extraction.
    """
    # Extract ONCE per video (process=False = no format selection yet, avoids
    # format-not-available errors), then reuse this dict for download + metadata.
    # Every extraction costs several player requests that YouTube counts
    # towards bot detection, so re-extracting is what triggered blocks.
    if raw is None:
        raw = ydl.extract_info(url, download=False, process=False)
    if not raw:
        print(f"  {C.R}✗  Could not fetch info for {url}{C.E}")
        return False
    title = raw.get('title') or raw.get('id') or url
    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.DM}[{i}/{total}]{C.E}  {C.W}{C.BO}{title}{C.E}")
    print(f"  {C.DG}│{C.E}  {C.DM}→ {out_dir}{C.E}")
    _ui_separator()
    # Reset phase tracker for this URL (video → audio → merge)
    _dl_phase_reset()
    # Full pipeline on the already-extracted info: format selection + download + post-process
    info = ydl.process_ie_result(raw, download=True)
    _save_video_metadata(info or raw, out_dir)
    # Remove from videolinks.txt if this batch came from there
    if from_videolinks:
        _remove_url_from_videolinks(url)
        print(f"  {C.G}✓{C.E}  {C.DM}Removed from videolinks.txt{C.E}")
    print()
    return True


def _download_urls(urls: list, out_dir: str, from_videolinks: bool = False):
    """Download a list of URLs via yt-dlp into out_dir, re-encode to MP4, save metadata.

    When from_videolinks=True each successfully downloaded URL is removed from
    videolinks.txt immediately after download.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print(f"{C.R}yt-dlp not installed. Run: pip install yt-dlp{C.E}")
        return

    os.makedirs(out_dir, exist_ok=True)

    quality_opts  = _pick_quality()
    cookie_opts   = _pick_cookie_source()
    cookie_mode   = cookie_opts.get('_cookie_mode', 'none')

    # ── Ultra High (4K/8K) mode — probe + resolve format per URL ────────
    if quality_opts.pop('_quality_mode', None) == 'ultra_high':
        uhd_pp = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        for i, url in enumerate(urls, 1):
            if i > 1:
                _polite_pause(i - 1)
            # Resolve UHD format for this URL
            while True:
                print(f"\n{C.CN}[{i}/{len(urls)}] Probing Ultra HD formats...{C.E}")
                try:
                    available, probed = _probe_uhd_formats(url, cookie_opts)
                except Exception as e:
                    print(f"\n{C.R}  Error: {str(e)[:200]}{C.E}")
                    _print_bot_block_help(len(urls) - i + 1, from_videolinks)
                    return
                if not available:
                    print(f"  {C.Y}No 4K/8K formats found for this video.{C.E}")
                    _ui_menu_item('1', 'Skip', C.CN, 'back to previous menu')
                    _ui_menu_item('2', 'Back to main menu', C.DG)
                    ch = _ui_prompt()
                    if ch == '2':
                        return
                    break  # skip this URL
                fmt = _pick_uhd_resolution(available)
                if fmt == '':  # user chose 'back' in the resolution picker
                    continue  # re-prompt probing (same URL)
                # Build per-URL opts
                url_quality = {
                    'format': fmt,
                    'merge_output_format': 'mp4',
                    'postprocessors': uhd_pp,
                }
                url_opts = _build_ydl_opts(out_dir, url_quality, cookie_opts)
                try:
                    with YoutubeDL(url_opts) as ydl:
                        _download_one(ydl, url, i, len(urls), out_dir,
                                      from_videolinks=from_videolinks, raw=probed)
                except Exception as e:
                    err_msg = str(e)
                    print(f"\n{C.R}  Error: {err_msg[:200]}{C.E}")
                    if _is_bot_error(err_msg):
                        _print_bot_block_help(len(urls) - i + 1, from_videolinks)
                        return
                break  # move to next URL
        print(f"  {C.G}{C.BO}✦{C.E}  {C.G}All done → {out_dir}{C.E}")
        return

    base_opts = _build_ydl_opts(out_dir, quality_opts, cookie_opts)

    print(f"\n  {C.G}{C.BO}⬢{C.E}  {C.W}{C.BO}Starting download of {len(urls)} video(s)...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}\n")

    failed_urls = []

    with YoutubeDL(base_opts) as ydl:
        for i, url in enumerate(urls, 1):
            try:
                _download_one(ydl, url, i, len(urls), out_dir,
                              from_videolinks=from_videolinks)
            except Exception as e:
                err_msg = str(e)
                print(f"\n  {C.R}✗  Error: {err_msg[:200]}{C.E}")

                # Bot block: stop right away — every further request deepens the flag
                if _is_bot_error(err_msg):
                    if cookie_mode == 'none':
                        print(f"  {C.Y}↳ Bot/auth block detected — will retry the rest with fresh cookies.{C.E}")
                        failed_urls = urls[i - 1:]
                    else:
                        _print_bot_block_help(len(urls) - i + 1, from_videolinks)
                    break
                print()
            if i < len(urls):
                _polite_pause(i)

    # ── Auto-retry with fresh cookies from the tool browser profile ────
    if failed_urls:
        _ui_header(f'Retrying {len(failed_urls)} blocked video(s) with fresh cookies', C.Y)
        retry_cookie_opts = _fresh_cookie_opts()
        if not retry_cookie_opts:
            _print_bot_block_help(len(failed_urls), from_videolinks)
        else:
            retry_opts = _build_ydl_opts(out_dir, quality_opts, retry_cookie_opts)
            with YoutubeDL(retry_opts) as ydl_retry:
                for i, url in enumerate(failed_urls, 1):
                    try:
                        _download_one(ydl_retry, url, i, len(failed_urls), out_dir,
                                      from_videolinks=from_videolinks)
                    except Exception as e:
                        err_msg = str(e)
                        print(f"\n  {C.R}✗  Retry failed: {err_msg[:200]}{C.E}\n")
                        if _is_bot_error(err_msg):
                            _print_bot_block_help(len(failed_urls) - i + 1, from_videolinks)
                            break
                    if i < len(failed_urls):
                        _polite_pause(i)

    print(f"\n  {C.DM}{'─' * 46}{C.E}")
    print(f"  {C.G}{C.BO}✦{C.E}  {C.G}All done → {out_dir}{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  MODE 2 — DOWNLOAD SINGLE VIDEO BY URL
# ═══════════════════════════════════════════════════════════════════════

def _print_video_stats(info: dict):
    """Print a concise statistics block for a single video."""
    _ui_header('Video Info', C.CN)
    print(f"  {C.DG}│{C.E} {C.CN}Title   :{C.E} {C.W}{info.get('title', '?')}{C.E}")
    print(f"  {C.DG}│{C.E} {C.CN}Channel :{C.E} {info.get('channel', info.get('uploader', '?'))}")
    print(f"  {C.DG}│{C.E} {C.CN}Date    :{C.E} {info.get('upload_date', '?')}")
    print(f"  {C.DG}│{C.E} {C.CN}Duration:{C.E} {info.get('duration_string', info.get('duration', '?'))}")
    print(f"  {C.DG}│{C.E} {C.CN}Views   :{C.E} {C.G}{info.get('view_count', '?')}{C.E}")
    print(f"  {C.DG}│{C.E} {C.CN}Likes   :{C.E} {C.G}{info.get('like_count', '?')}{C.E}")
    print(f"  {C.DG}│{C.E} {C.CN}Comments:{C.E} {info.get('comment_count', '?')}")
    print(f"  {C.DG}│{C.E} {C.CN}Res     :{C.E} {info.get('resolution', '?')}  FPS: {info.get('fps', '?')}")
    cats = ', '.join(info.get('categories', []))
    if cats:
        print(f"  {C.DG}│{C.E} {C.CN}Category:{C.E} {cats}")
    tags = info.get('tags', [])
    if tags:
        print(f"  {C.DG}│{C.E} {C.CN}Tags    :{C.E} {', '.join(tags[:10])}{'...' if len(tags) > 10 else ''}")
    _ui_separator()
    print()


def mode_download_single(km: KeyManager):
    """Download a single video by URL — shows stats then offers download / thumbnail options."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        print(f"{C.R}yt-dlp not installed. Run: pip install yt-dlp{C.E}")
        return

    url = input(f"\n  {C.BO}Paste video URL:{C.E} ").strip()
    if not url:
        return

    # ── Fetch stats via yt-dlp (no download, no API quota used) ────────
    print(f"  {C.CN}Fetching video info...{C.E}")
    try:
        with YoutubeDL({'quiet': True, 'no_warnings': True,
                        'logger': _YtLogger(), 'skip_download': True,
                        'js_runtimes': {'node': {}},
                        'remote_components': ['ejs:github'],
                        'extractor_args': _YT_EXTRACTOR_ARGS}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"  {C.R}✗  Could not fetch info: {e}{C.E}")
        info = None

    if info:
        _print_video_stats(info)
    else:
        print(f"  {C.Y}⚠  Could not load video stats (URL may be private/geo-blocked).{C.E}\n")

    # ── Sub-menu ────────────────────────────────────────────────────────
    while True:
        _ui_header('Actions', C.CN)
        _ui_menu_item('1', 'Download video', C.G, 'MP4 | MP3 — quality + cookies')
        _ui_menu_item('2', 'Download thumbnail', C.CN, 'max resolution')
        _ui_menu_back('0', 'Back to main menu')
        ch = _ui_prompt()

        if ch == '1':
            _download_urls([url], DOWNLOADS_DIR)
            break
        elif ch == '2':
            # Extract video ID for thumbnail download
            m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
            if not m:
                print(f"{C.R}  Could not extract video ID from URL.{C.E}")
                break
            vid = m.group(1)
            title = info.get('title', vid) if info else vid
            print(f"  {C.CN}⟳  Downloading thumbnail for: {C.W}{title}{C.E}")
            _download_single_thumbnail(vid, title)
            print(f"  {C.G}✦  Done → {THUMBS_DIR}{C.E}")
            break
        elif ch == '0':
            break


def download_selected(results: list):
    """Let user pick which search results to download."""
    try:
        from yt_dlp import YoutubeDL  # noqa: F401
    except ImportError:
        print(f"{C.R}yt-dlp not installed. pip install yt-dlp{C.E}")
        return

    items = [r for r in results if r['id'].get('videoId')]
    if not items:
        print(f"  {C.Y}No downloadable videos.{C.E}")
        return

    print(f"\n  {C.CN}Enter numbers (e.g. 1,3,5) or{C.E} {C.W}all{C.E}{C.CN}:{C.E}")
    ch = _ui_prompt().lower()
    if ch == 'all':
        sel = items
    else:
        try:
            idxs = [int(x.strip()) - 1 for x in ch.split(',')]
            sel = [items[i] for i in idxs if 0 <= i < len(items)]
        except (ValueError, IndexError):
            print(f"  {C.R}Invalid input.{C.E}")
            return
    if not sel:
        print(f"  {C.Y}Nothing selected.{C.E}")
        return

    urls = [f"https://www.youtube.com/watch?v={it['id']['videoId']}" for it in sel]
    _download_urls(urls, DOWNLOADS_DIR)


def search_post_menu(results: list, query: str, km: KeyManager, page_size: int = 25) -> str:
    """After-search actions. Returns 'search' to loop, 'menu' to go back."""
    while True:
        _ui_header(f'Actions ({len(results)} result(s) loaded)', C.CN)
        _ui_menu_item('1', 'Save ALL results → find.txt', C.G)
        _ui_menu_item('2', 'Show results again', C.CN, 'paginated')
        _ui_menu_item('3', 'Download thumbnails', C.CN, 'max resolution')
        _ui_menu_item('4', 'Download videos', C.G, 'yt-dlp → MP4')
        _ui_menu_item('5', 'Show channel analytics', C.B)
        _ui_menu_item('6', 'New search', C.Y)
        _ui_menu_back('0', 'Back to main menu')
        ch = _ui_prompt()

        if ch == '1':
            print(f"  {C.CN}⟳  Saving all {len(results)} result(s) to find.txt...{C.E}")
            save_results(results, query)
        elif ch == '2':
            cids = list({it['snippet'].get('channelId', '')
                         for it in results if it['snippet'].get('channelId')})
            ch_stats = get_channel_stats(km, cids)
            display_results_paginated(results, ch_stats, page_size)
        elif ch == '3':
            download_thumbnails_search(results)
        elif ch == '4':
            download_selected(results)
        elif ch == '5':
            cids = list({it['snippet'].get('channelId', '')
                         for it in results if it['snippet'].get('channelId')})
            stats = get_channel_stats(km, cids)
            if stats:
                _ui_header('Channel Analytics', C.B)
                for cid, s in stats.items():
                    print(f"  {C.DG}│{C.E} {C.CN}{s['title']}{C.E}")
                    print(f"  {C.DG}│{C.E}  {C.DM}Subs: {C.E}{C.W}{s['subs']}{C.E}  "
                          f"{C.DM}Videos: {C.E}{C.W}{s['vids']}{C.E}  "
                          f"{C.DM}Views: {C.E}{C.W}{s['views']}{C.E}")
            else:
                print(f"  {C.Y}⚠  Could not load channel stats.{C.E}")
        elif ch == '6':
            return 'search'
        elif ch == '0':
            return 'menu'


def mode_search(km: KeyManager):
    """Search mode loop."""
    while True:
        query = input(f"\n  {C.BO}Search query{C.E} {C.DM}(or 'back'){C.E}: ").strip()
        if query.lower() in ('back', 'exit', 'quit'):
            return
        if not query:
            continue

        filters = ask_filters()
        page_size = filters.get('page_size', 25)

        print(f"\n  {C.CN}⟳  Searching for {C.W}'{query}'{C.E}{C.CN}...{C.E}")
        results = search_youtube_all(km, query, filters)

        if not results:
            print(f"  {C.Y}No results found.{C.E}")
            continue

        # Fetch channel stats for the first batch to display alongside results
        cids = list({it['snippet'].get('channelId', '')
                     for it in results if it['snippet'].get('channelId')})
        ch_stats = get_channel_stats(km, cids)

        display_results_paginated(results, ch_stats, page_size)

        action = search_post_menu(results, query, km, page_size)
        if action == 'menu':
            return
        # action == 'search' → loops back


# ═══════════════════════════════════════════════════════════════════════
#  MODE 2 — PARSE CHANNEL
# ═══════════════════════════════════════════════════════════════════════

def resolve_channel_id(km: KeyManager, user_input: str):
    """
    Accept:
      https://www.youtube.com/channel/UC...
      https://www.youtube.com/@handle
      @handle  (ASCII or Unicode, e.g. @ОльгаКиселёва)
      URL-encoded handles (e.g. @%D0%9E%D0%BB%D1%8C%D0%B3%D0%B0)
    Returns (channel_id, channel_title) or (None, None).
    """
    user_input = user_input.strip()

    # URL-decode so percent-encoded Unicode handles become readable
    user_input = urllib.parse.unquote(user_input)

    # Direct channel URL
    m = re.search(r'youtube\.com/channel/(UC[\w-]+)', user_input)
    if m:
        cid = m.group(1)
        resp = api_call(km, lambda yt: yt.channels().list(part="snippet", id=cid))
        if resp and resp.get('items'):
            return cid, resp['items'][0]['snippet']['title']
        return cid, cid

    # @handle (in URL or standalone) — Unicode-aware regex
    m = re.search(r'@([\w.\-]+)', user_input, re.UNICODE)
    if m:
        handle = m.group(1)  # without @
        # Try forHandle first (YouTube API v3 supports it on channels().list)
        resp = api_call(km, lambda yt: yt.channels().list(
            part="snippet", forHandle=handle))
        if resp and resp.get('items'):
            it = resp['items'][0]
            return it['id'], it['snippet']['title']
        # Fallback: search with @handle
        resp = api_call(km, lambda yt: yt.search().list(
            part="snippet", q='@' + handle, type="channel", maxResults=1))
        if resp and resp.get('items'):
            it = resp['items'][0]
            return it['snippet']['channelId'], it['snippet']['title']

    # Try as free-text search
    resp = api_call(km, lambda yt: yt.search().list(
        part="snippet", q=user_input, type="channel", maxResults=1))
    if resp and resp.get('items'):
        it = resp['items'][0]
        return it['snippet']['channelId'], it['snippet']['title']

    return None, None


def fetch_all_channel_videos(km: KeyManager, channel_id: str) -> list:
    """Paginate through ALL videos on a channel using the uploads playlist.

    Uses playlistItems().list() instead of search().list() because:
      - search().list() caps results at ~500 and costs 100 quota units/call
      - playlistItems().list() returns ALL videos and costs only 1 quota unit/call

    The uploads playlist ID is derived by replacing the 'UC' prefix with 'UU'.
    """
    # Derive the uploads playlist ID from the channel ID
    if channel_id.startswith('UC'):
        uploads_playlist_id = 'UU' + channel_id[2:]
    else:
        # Fallback: fetch the uploads playlist ID from the channel resource
        resp = api_call(km, lambda yt: yt.channels().list(
            part="contentDetails", id=channel_id))
        if not resp or not resp.get('items'):
            print(f"{C.R}Could not resolve uploads playlist for channel.{C.E}")
            return []
        uploads_playlist_id = (resp['items'][0]
                               .get('contentDetails', {})
                               .get('relatedPlaylists', {})
                               .get('uploads'))
        if not uploads_playlist_id:
            print(f"{C.R}Channel has no uploads playlist.{C.E}")
            return []

    videos = []
    page_token = None

    while True:
        def req(yt, pt=page_token):
            params = dict(part="snippet", playlistId=uploads_playlist_id,
                          maxResults=50)
            if pt:
                params['pageToken'] = pt
            return yt.playlistItems().list(**params)

        resp = api_call(km, req)
        if not resp:
            break

        for it in resp.get('items', []):
            resource = it.get('snippet', {}).get('resourceId', {})
            vid = resource.get('videoId')
            if vid:
                videos.append(dict(
                    videoId=vid,
                    title=it['snippet'].get('title', ''),
                    publishedAt=it['snippet'].get('publishedAt', ''),
                ))

        page_token = resp.get('nextPageToken')
        if not page_token:
            break
        print(f"  ... fetched {len(videos)} so far")

    return videos


def classify_videos(km: KeyManager, videos: list):
    """Get durations via videos().list and split into longs (>60s) & shorts (≤60s)."""
    longs, shorts = [], []

    for i in range(0, len(videos), 50):
        chunk = videos[i:i + 50]
        ids_str = ','.join(v['videoId'] for v in chunk)

        resp = api_call(km, lambda yt: yt.videos().list(
            part="contentDetails,snippet", id=ids_str))
        if not resp:
            continue

        for it in resp.get('items', []):
            dur = it.get('contentDetails', {}).get('duration', 'PT0S')
            secs = parse_iso_duration(dur)
            entry = dict(
                videoId=it['id'],
                title=it['snippet']['title'],
                seconds=secs,
            )
            if secs <= 60:
                shorts.append(entry)
            else:
                longs.append(entry)

    return longs, shorts


def _copy_urls_to_videolinks(urls: list):
    """
    Append urls to videolinks.txt WITHOUT removing originals from parsed files.
    Skips lines already present in videolinks.txt to avoid duplicates.
    """
    os.makedirs(os.path.dirname(VIDEOLINKS) or '.', exist_ok=True)
    # Read existing URLs in videolinks.txt
    existing = set()
    if os.path.isfile(VIDEOLINKS):
        with open(VIDEOLINKS, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    existing.add(s)

    new_urls = [u for u in urls if u not in existing]
    if not new_urls:
        print(f"  {C.Y}All URLs already present in videolinks.txt — nothing added.{C.E}")
        return

    with open(VIDEOLINKS, 'a', encoding='utf-8') as f:
        for u in new_urls:
            f.write(u + '\n')
    print(f"  {C.G}Added {len(new_urls)} URL(s) to videolinks.txt{C.E}")


def _download_thumbnails_for_urls(urls: list, channel_subdir: str, titles: dict = None):
    """
    Download max-res thumbnails for a list of YouTube video URLs.
    Saves to thumbnails/<channel_subdir>/ folder.
    Names each thumbnail after the video title: "{title} [{vid}].jpg"
    (consistent with _download_single_thumbnail / thumb_channel naming).
    """
    thumb_dir = os.path.join(THUMBS_DIR, channel_subdir)
    os.makedirs(thumb_dir, exist_ok=True)
    total = len(urls)
    ok = 0

    # ── Resolve video titles via yt-dlp (no download, no API quota) ─────
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        YoutubeDL = None

    # vid → title. Titles passed in (from the Data API) cost no YouTube player requests;
    # only the missing ones are fetched via yt-dlp, with pauses to avoid bot detection.
    title_cache = dict(titles or {})
    missing = []
    for url in urls:
        m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
        if m and m.group(1) not in title_cache:
            missing.append(url)
    if YoutubeDL is not None and missing:
        print(f"  {C.CN}Fetching video titles for thumbnails...{C.E}")
        probe_opts = {
            'quiet': True, 'no_warnings': True,
            'logger': _YtLogger(), 'skip_download': True,
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
            'extractor_args': _YT_EXTRACTOR_ARGS,
            'sleep_interval_requests': 1,
        }
        try:
            with YoutubeDL(probe_opts) as ydl:
                for n, url in enumerate(missing, 1):
                    try:
                        info = ydl.extract_info(url, download=False, process=False)
                        if info:
                            title_cache[info.get('id', '')] = info.get('title', '')
                    except Exception as e:
                        if _is_bot_error(str(e)):
                            print(f"  {C.Y}⚠  Rate-limited — remaining thumbnails will be named by video ID.{C.E}")
                            break
                    if n < len(missing):
                        time.sleep(random.uniform(1.5, 3.5))
        except Exception:
            pass

    for i, url in enumerate(urls, 1):
        m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
        if not m:
            print(f"  {C.Y}⚠  Cannot extract video ID from: {url}{C.E}")
            continue
        vid = m.group(1)
        title = title_cache.get(vid, '')
        if title:
            safe_title = safe_filename(title)
            fname = os.path.join(thumb_dir, f"{safe_title} [{vid}].jpg")
            display = safe_title
        else:
            fname = os.path.join(thumb_dir, f"{vid}.jpg")
            display = vid
        img_url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
        try:
            urllib.request.urlretrieve(img_url, fname)
            if os.path.getsize(fname) < 5000:
                img_url = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                urllib.request.urlretrieve(img_url, fname)
            ok += 1
            print(f"  {C.G}[{i}/{total}] ✓{C.E} {display}")
        except Exception as e:
            print(f"  {C.R}[{i}/{total}] ✗ {display}: {e}{C.E}")
    print(f"  {C.G}Thumbnails done: {ok}/{total} → {thumb_dir}{C.E}")


def _parse_download_submenu(urls: list, label: str, channel_subdir: str,
                            titles: dict = None):
    """
    Inner submenu shown after video-type selection.
    label     — human-readable name, e.g. 'Long videos' or 'Shorts'
    channel_subdir — subfolder name for thumbnails
    titles    — optional {videoId: title} for thumbnail filenames
    """
    while True:
        _ui_header(f'Download: {label} ({len(urls)} videos)', C.G)
        _ui_menu_item('1', 'Download video', C.G)
        _ui_menu_item('2', 'Download video + thumbnails', C.CN)
        _ui_menu_back('0', 'Back')
        ch = _ui_prompt()

        if ch == '0':
            return

        if ch not in ('1', '2'):
            print(f"  {C.Y}Invalid choice.{C.E}")
            continue

        # Copy URLs into videolinks.txt (without removing them from parsed files)
        print(f"\n  {C.CN}⟳  Copying {len(urls)} URL(s) to videolinks.txt...{C.E}")
        _copy_urls_to_videolinks(urls)

        # Re-read only the URLs we just added (they may have been filtered for dups)
        # We pass them directly — simpler and avoids re-reading the file
        _download_urls(urls, DOWNLOADS_DIR, from_videolinks=True)

        # If user chose option 2 — also download thumbnails
        if ch == '2':
            print(f"\n  {C.CN}⟳  Downloading thumbnails for {C.W}{label}{C.E}{C.CN}...{C.E}")
            _download_thumbnails_for_urls(urls, channel_subdir, titles)

        return


def mode_parse(km: KeyManager):
    """Channel parsing mode with post-parse download menu."""
    _ui_header('Channel Parser', C.H)
    print(f"  {C.DM}Paste a channel URL or @handle (e.g. @MrBeast){C.E}")
    user_in = input(f"  {C.CN}›{C.E} ").strip()
    if not user_in:
        return

    print(f"  {C.CN}⟳  Resolving channel...{C.E}")
    cid, ctitle = resolve_channel_id(km, user_in)
    if not cid:
        print(f"  {C.R}✗  Channel not found.{C.E}")
        return

    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.G}{C.BO}Channel:{C.E}  {C.W}{ctitle}{C.E}  {C.DM}({cid}){C.E}")
    _ui_separator()
    print(f"  {C.CN}⟳  Fetching all videos (may take a while)...{C.E}")

    all_vids = fetch_all_channel_videos(km, cid)
    if not all_vids:
        print(f"  {C.Y}⚠  No videos found.{C.E}")
        return

    print(f"  {C.G}✓  Fetched {len(all_vids)} video(s){C.E}")
    print(f"  {C.CN}⟳  Classifying long vs. shorts...{C.E}")

    longs, shorts = classify_videos(km, all_vids)

    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.W}{C.BO}{ctitle}{C.E}")
    print(f"  {C.DG}│{C.E} {C.G}Long videos (>60 s): {C.W}{C.BO}{len(longs)}{C.E}")
    print(f"  {C.DG}│{C.E} {C.Y}Shorts     (≤60 s): {C.W}{C.BO}{len(shorts)}{C.E}")
    _ui_separator()

    # ── Save to parsed/ ─────────────────────────────────────────────────
    os.makedirs(PARSED_DIR, exist_ok=True)
    safe_name = safe_filename(ctitle)

    long_path  = os.path.join(PARSED_DIR, f"{safe_name}_long.txt")
    short_path = os.path.join(PARSED_DIR, f"{safe_name}_shorts.txt")

    long_urls  = [f"https://www.youtube.com/watch?v={v['videoId']}" for v in longs]
    short_urls = [f"https://www.youtube.com/watch?v={v['videoId']}" for v in shorts]
    title_map  = {v['videoId']: v['title'] for v in longs + shorts}

    with open(long_path, 'w', encoding='utf-8') as f:
        for u in long_urls:
            f.write(u + '\n')

    with open(short_path, 'w', encoding='utf-8') as f:
        for u in short_urls:
            f.write(u + '\n')

    print(f"  {C.G}✓{C.E}  {C.DM}Saved → {long_path}{C.E}")
    print(f"  {C.G}✓{C.E}  {C.DM}Saved → {short_path}{C.E}")

    # ── Post-parse download menu ─────────────────────────────────────────
    while True:
        _ui_header('Download Options', C.G)
        _ui_menu_item('1', f'Download long videos', C.G, f'{len(longs)} videos')
        _ui_menu_item('2', f'Download shorts', C.Y, f'{len(shorts)} videos')
        _ui_menu_item('3', f'Download long + shorts', C.CN, f'{len(longs) + len(shorts)} videos')
        _ui_menu_back('0', 'Back to main menu')
        ch = _ui_prompt()

        if ch == '0':
            return
        elif ch == '1':
            if not long_urls:
                print(f"  {C.Y}⚠  No long videos found on this channel.{C.E}")
                continue
            _parse_download_submenu(long_urls, 'Long videos', f"{safe_name}_long", title_map)
        elif ch == '2':
            if not short_urls:
                print(f"  {C.Y}⚠  No shorts found on this channel.{C.E}")
                continue
            _parse_download_submenu(short_urls, 'Shorts', f"{safe_name}_shorts", title_map)
        elif ch == '3':
            all_urls = long_urls + short_urls
            if not all_urls:
                print(f"  {C.Y}⚠  No videos found on this channel.{C.E}")
                continue
            _parse_download_submenu(all_urls, 'Long + Shorts', f"{safe_name}_all", title_map)
        else:
            print(f"  {C.Y}Invalid choice.{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  MODE 3 — BATCH DOWNLOAD FROM videolinks.txt
# ═══════════════════════════════════════════════════════════════════════

def mode_download():
    """Read URLs from videolinks.txt and download them all."""
    if not os.path.exists(VIDEOLINKS):
        print(f"  {C.R}✗  File not found: {VIDEOLINKS}{C.E}")
        print(f"  {C.DM}Create it and put one YouTube URL per line.{C.E}")
        # Create an empty template
        with open(VIDEOLINKS, 'w', encoding='utf-8') as f:
            f.write("# Put one YouTube video URL per line\n")
        print(f"  {C.Y}+  Created empty template → {VIDEOLINKS}{C.E}")
        return

    with open(VIDEOLINKS, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f
                if line.strip() and not line.strip().startswith('#')]

    if not urls:
        print(f"  {C.Y}⚠  No URLs in {VIDEOLINKS}{C.E}")
        return

    _ui_separator()
    print(f"  {C.G}{C.BO}Found {len(urls)} URL(s) in videolinks.txt{C.E}")
    for i, u in enumerate(urls, 1):
        print(f"  {C.DG}│{C.E} {C.DM}{i}.{C.E} {u}")
    _ui_separator()

    _download_urls(urls, DOWNLOADS_DIR, from_videolinks=True)


# ═══════════════════════════════════════════════════════════════════════
#  MODE 4 — THUMBNAILS
# ═══════════════════════════════════════════════════════════════════════

def _download_single_thumbnail(video_id: str, title: str):
    """Download a single max-res thumbnail, named after video title."""
    os.makedirs(THUMBS_DIR, exist_ok=True)
    safe_title = safe_filename(title)
    fname = os.path.join(THUMBS_DIR, f"{safe_title} [{video_id}].jpg")
    url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    try:
        urllib.request.urlretrieve(url, fname)
        if os.path.getsize(fname) < 5000:
            url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            urllib.request.urlretrieve(url, fname)
        print(f"  {C.G}✓{C.E} {safe_title}")
    except Exception as e:
        print(f"  {C.R}✗ {video_id}: {e}{C.E}")


def thumb_single(km: KeyManager):
    """Download thumbnail from a single video URL."""
    url = input(f"\n  {C.BO}Paste video URL:{C.E} ").strip()
    if not url:
        return

    # Extract video ID
    m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
    if not m:
        print(f"  {C.R}✗  Could not extract video ID from URL.{C.E}")
        return
    vid = m.group(1)

    # Get title via API
    resp = api_call(km, lambda yt: yt.videos().list(part="snippet", id=vid))
    if resp and resp.get('items'):
        title = resp['items'][0]['snippet']['title']
    else:
        title = vid

    print(f"  {C.CN}⟳  Downloading thumbnail for: {C.W}{title}{C.E}")
    _download_single_thumbnail(vid, title)
    print(f"  {C.G}✦  Done → {THUMBS_DIR}{C.E}")


def thumb_channel(km: KeyManager):
    """Download all thumbnails from a channel."""
    user_in = input(f"\n  {C.BO}Paste channel URL or @handle:{C.E} ").strip()
    if not user_in:
        return

    print(f"  {C.CN}⟳  Resolving channel...{C.E}")
    cid, ctitle = resolve_channel_id(km, user_in)
    if not cid:
        print(f"  {C.R}✗  Channel not found.{C.E}")
        return

    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.G}{C.BO}Channel:{C.E}  {C.W}{ctitle}{C.E}")
    _ui_separator()
    print(f"  {C.CN}⟳  Fetching videos...{C.E}")

    all_vids = fetch_all_channel_videos(km, cid)
    if not all_vids:
        print(f"  {C.Y}⚠  No videos found.{C.E}")
        return

    print(f"  {C.G}✓  Found {len(all_vids)} video(s). Downloading thumbnails...{C.E}")
    os.makedirs(THUMBS_DIR, exist_ok=True)

    count = 0
    total = len(all_vids)
    for v in all_vids:
        vid = v['videoId']
        title = safe_filename(v['title'])
        fname = os.path.join(THUMBS_DIR, f"{title} [{vid}].jpg")
        url = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
        try:
            urllib.request.urlretrieve(url, fname)
            if os.path.getsize(fname) < 5000:
                url = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                urllib.request.urlretrieve(url, fname)
            count += 1
            print(f"  {C.G}✓{C.E}  {C.DM}[{count}/{total}]{C.E}  {title}")
        except Exception as e:
            print(f"  {C.R}✗  {C.DM}[{count+1}/{total}]{C.E}  {vid}: {e}{C.E}")

    _ui_separator()
    print(f"  {C.G}{C.BO}✦{C.E}  {C.G}Downloaded {count}/{total} thumbnail(s) → {THUMBS_DIR}{C.E}")
    _ui_separator()


def mode_thumbnails(km: KeyManager):
    """Thumbnail download menu."""
    _ui_header('Thumbnails', C.CN)
    _ui_menu_item('1', 'Download from single video URL', C.CN)
    _ui_menu_item('2', 'Download all from a channel', C.G)
    _ui_menu_back('0', 'Back')
    ch = _ui_prompt()

    if ch == '1':
        thumb_single(km)
    elif ch == '2':
        thumb_channel(km)


# ═══════════════════════════════════════════════════════════════════════
#  MODE 6 — PLAYLIST PARSER
# ═══════════════════════════════════════════════════════════════════════

def _extract_playlist_id(user_input: str):
    """
    Extract a YouTube playlist ID from a URL or raw ID.
    Accepts:
      https://www.youtube.com/playlist?list=PLxxxxxxxx
      https://www.youtube.com/watch?v=xxx&list=PLxxxxxxxx
      PLxxxxxxxx  (raw ID)
    Returns playlist_id string or None.
    """
    user_input = user_input.strip()
    m = re.search(r'[?&]list=([A-Za-z0-9_-]+)', user_input)
    if m:
        return m.group(1)
    # Raw playlist ID: starts with PL, UU, RD, FL, etc.
    if re.match(r'^[A-Za-z]{2}[A-Za-z0-9_-]{10,}$', user_input):
        return user_input
    return None


def _fetch_playlist_info(km, playlist_id: str):
    """
    Fetch playlist title and total video count.
    Returns (title, item_count) or (playlist_id, '?') on failure.
    """
    resp = api_call(km, lambda yt: yt.playlists().list(
        part='snippet,contentDetails', id=playlist_id))
    if resp and resp.get('items'):
        item = resp['items'][0]
        title = item['snippet'].get('title', playlist_id)
        count = item.get('contentDetails', {}).get('itemCount', '?')
        return title, count
    return playlist_id, '?'


def fetch_playlist_videos(km, playlist_id: str) -> list:
    """
    Fetch ALL videos from a playlist via playlistItems().list() with pagination.
    Returns list of dicts: {videoId, title, publishedAt, position}.
    Costs 1 quota unit per page (50 items).
    """
    videos = []
    page_token = None

    while True:
        def req(yt, pt=page_token):
            params = dict(part='snippet,contentDetails',
                          playlistId=playlist_id,
                          maxResults=50)
            if pt:
                params['pageToken'] = pt
            return yt.playlistItems().list(**params)

        resp = api_call(km, req)
        if not resp:
            break

        for it in resp.get('items', []):
            sn = it.get('snippet', {})
            cd = it.get('contentDetails', {})
            vid = sn.get('resourceId', {}).get('videoId') or cd.get('videoId')
            if not vid:
                continue
            # Skip deleted / private videos
            title = sn.get('title', '')
            if title in ('Deleted video', 'Private video'):
                continue
            videos.append(dict(
                videoId=vid,
                title=title,
                publishedAt=sn.get('publishedAt', ''),
                position=sn.get('position', len(videos)),
            ))

        page_token = resp.get('nextPageToken')
        if not page_token:
            break
        print(f"  {C.DM}⟳  Fetched {len(videos)} so far...{C.E}")

    return videos


def _print_playlist_summary(title: str, playlist_id: str, videos: list):
    """Print a styled summary block for the parsed playlist."""
    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.CN}{C.BO}Playlist :{C.E} {C.W}{title}{C.E}")
    print(f"  {C.DG}│{C.E} {C.CN}ID       :{C.E} {C.DM}{playlist_id}{C.E}")
    print(f"  {C.DG}│{C.E} {C.CN}Videos   :{C.E} {C.G}{C.BO}{len(videos)}{C.E} {C.DM}(accessible){C.E}")
    _ui_separator()
    # Show first 5 as preview
    preview = videos[:5]
    for v in preview:
        pos = v.get('position', 0) + 1
        t = v['title'][:60] + ('...' if len(v['title']) > 60 else '')
        print(f"  {C.DG}│{C.E} {C.DM}{pos:3}.{C.E} {t}")
    if len(videos) > 5:
        print(f"  {C.DG}│{C.E}  {C.DM}... and {len(videos) - 5} more{C.E}")
    _ui_separator()
    print()


def mode_playlist(km):
    """Playlist Parser mode — parse a playlist then offer download options."""
    _ui_banner('Playlist Parser', 52, C.H)
    print(f"  {C.DM}Paste a YouTube playlist URL or ID{C.E}")
    print(f"  {C.DG}│{C.E} {C.DM}Example: https://youtube.com/playlist?list=PLxxxxxx{C.E}")
    print(f"  {C.DG}│{C.E} {C.DM}         PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx{C.E}\n")
    user_in = input(f"  {C.CN}›{C.E} ").strip()
    if not user_in:
        return

    playlist_id = _extract_playlist_id(user_in)
    if not playlist_id:
        print(f"  {C.R}✗  Could not extract a playlist ID from that input.{C.E}")
        print(f"  {C.Y}  Make sure the URL contains ?list= or paste the raw PL... ID.{C.E}")
        return

    # ── Fetch playlist metadata ─────────────────────────────────────────
    print(f"  {C.CN}⟳  Fetching playlist info...{C.E}")
    pl_title, pl_count = _fetch_playlist_info(km, playlist_id)

    print(f"  {C.CN}⟳  Fetching all videos in playlist{C.E} {C.DM}(reported: {pl_count}){C.E}{C.CN}...{C.E}")
    videos = fetch_playlist_videos(km, playlist_id)

    if not videos:
        print(f"  {C.Y}⚠  No accessible videos found in this playlist.{C.E}")
        return

    _print_playlist_summary(pl_title, playlist_id, videos)

    urls = [f"https://www.youtube.com/watch?v={v['videoId']}" for v in videos]
    safe_name = safe_filename(pl_title)
    thumb_subdir = safe_name or playlist_id

    # ── Save playlist URLs to parsed/ ───────────────────────────────────
    os.makedirs(PARSED_DIR, exist_ok=True)
    playlist_file = os.path.join(PARSED_DIR, f"{safe_name or playlist_id}_playlist.txt")
    with open(playlist_file, 'w', encoding='utf-8') as f:
        f.write(f"# Playlist: {pl_title}\n")
        f.write(f"# ID: {playlist_id}\n")
        f.write(f"# Parsed: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Total: {len(videos)} videos\n\n")
        for v in videos:
            f.write(f"https://www.youtube.com/watch?v={v['videoId']}\n")
    print(f"  {C.G}✓{C.E}  {C.DM}Saved → {playlist_file}{C.E}\n")

    # ── Post-parse menu ─────────────────────────────────────────────────
    while True:
        _ui_header(f'Playlist Actions  [{len(videos)} videos]', C.G)
        _ui_menu_item('1', 'Download videos', C.G, 'MP4 | MP3 — quality + cookies')
        _ui_menu_item('2', 'Download thumbnails', C.CN,
                      f'→ thumbnails/{thumb_subdir}/')
        _ui_menu_back('0', 'Back to main menu')
        ch = _ui_prompt()

        if ch == '0':
            return

        elif ch == '1':
            _download_urls(urls, DOWNLOADS_DIR)

        elif ch == '2':
            print(f"\n  {C.CN}⟳  Downloading {len(urls)} thumbnail(s)...{C.E}")
            _download_thumbnails_for_urls(
                urls, thumb_subdir, {v['videoId']: v['title'] for v in videos})

        else:
            print(f"  {C.Y}⚠  Invalid choice.{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════════

def main():
    os.system('')  # enable ANSI colours on Windows

    # ── Gemini CLI-style ASCII banner ──
    _print_cfinder_banner()

    # ── Animated dependency loading + environment check ──
    _animated_startup()

    # ── Load API keys (still uses original styled output) ──
    km = KeyManager(API_KEYS_FILE)
    check_key_quotas(km)

    while True:
        _ui_banner('Main Menu', 52, C.CN)
        _ui_menu_item('1', 'Search videos', C.G)
        _ui_menu_item('2', 'Download single video by URL', C.CN)
        _ui_menu_item('3', 'Parse channel (long | shorts)', C.H)
        _ui_menu_item('4', 'Download from videolinks.txt', C.Y)
        _ui_menu_item('5', 'Download thumbnails', C.B)
        _ui_menu_item('6', 'Playlist Parser', C.H)
        _ui_separator()
        _ui_menu_back('0', 'Exit')

        choice = _ui_prompt()

        if choice == '1':
            mode_search(km)
        elif choice == '2':
            mode_download_single(km)
        elif choice == '3':
            mode_parse(km)
        elif choice == '4':
            mode_download()
        elif choice == '5':
            mode_thumbnails(km)
        elif choice == '6':
            mode_playlist(km)
        elif choice == '0':
            break
        else:
            print(f"  {C.Y}⚠  Invalid choice, try again.{C.E}")

    print(f"\n  {C.G}{C.BO}Goodbye! 👋{C.E}")
    input("  Press Enter to close...")


if __name__ == "__main__":
    main()

