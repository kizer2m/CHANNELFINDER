#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Channel Finder v4.3.0
  Mode 1 — Search videos (filters, thumbnails, channel stats, download)
  Mode 2 — Download single video by URL (stats + download/thumbnail)
  Mode 3 — Parse channel (long / shorts) + download menu (long/shorts/both + thumbnails)
  Mode 4 — Batch download from videolinks.txt (re-encode to MP4 + metadata)
  Mode 5 — Download thumbnails
"""

import os
import sys
import re
import urllib.parse
import json
import subprocess
import urllib.request
import msvcrt
import time
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
    num = f"  {dot} {accent}{C.BO}{key}.{C.E}"
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
    print(f"         {C.DG}YouTube Channel Finder{C.E}  {C.DM}│{C.E}  {C.W}{C.BO}v4.3.0{C.E}")
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
    deps = [
        ('google-api-python-client', 'Google API Client'),
        ('yt-dlp',                   'yt-dlp downloader'),
    ]

    g_cyan  = '\033[38;5;44m'
    g_green = '\033[38;5;49m'
    g_blue  = '\033[38;5;39m'

    print(f"  {g_blue}{C.BO}⬢{C.E}  {C.W}{C.BO}Installing | updating dependencies...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}\n")

    for idx, (pkg, label) in enumerate(deps):
        # Animate progress bar filling up
        total_steps = 20
        for step in range(total_steps + 1):
            progress = step / total_steps
            bar = _progress_bar_str(progress, 30, g_cyan if idx == 0 else g_green)
            pct = int(progress * 100)
            spinner = next(_spinner_gen)
            status_text = 'checking' if step < total_steps // 2 else 'updating'
            print(f"\r  {g_cyan}{spinner}{C.E}  {C.W}{label}{C.E}  {bar}  {C.DM}{pct:3d}%{C.E}  {C.DG}{status_text}{C.E}   ", end='', flush=True)
            time.sleep(0.02)

        # Actually check / update the package
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', pkg],
                capture_output=True, text=True, timeout=60,
            )
            if 'Successfully installed' in result.stdout:
                ver = ''
                for word in result.stdout.split():
                    if pkg.replace('-', '') in word.replace('-', '').lower():
                        ver = word
                        break
                status_icon = f"{C.G}{C.BO}✓{C.E}"
                status_msg  = f"{C.G}updated{C.E}" + (f" {C.DM}({ver}){C.E}" if ver else '')
            else:
                status_icon = f"{C.G}{C.BO}✓{C.E}"
                status_msg  = f"{C.G}up to date{C.E}"
        except Exception as e:
            status_icon = f"{C.Y}{C.BO}⚠{C.E}"
            status_msg  = f"{C.Y}skipped ({e}){C.E}"

        bar_done = _progress_bar_str(1.0, 30, g_green)
        print(f"\r  {status_icon}  {C.W}{label}{C.E}  {bar_done}  {C.DM}100%{C.E}  {status_msg}           ")

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

def check_updates():
    print(f"  {C.CN}{C.BO}⟳{C.E}  {C.W}Checking for yt-dlp updates...{C.E}", end='', flush=True)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            capture_output=True, text=True, timeout=60,
        )
        if 'Successfully installed' in result.stdout:
            # Extract the new version from pip output
            ver = ''
            for word in result.stdout.split():
                if 'yt' in word.lower() and '-' in word:
                    ver = word
                    break
            print(f"\r  {C.G}{C.BO}✓{C.E}  {C.G}yt-dlp updated{C.E}" +
                  (f" {C.DM}({ver}){C.E}" if ver else '') + '          ')
        else:
            print(f"\r  {C.G}{C.BO}✓{C.E}  {C.G}yt-dlp is up to date{C.E}          ")
    except Exception as e:
        print(f"\r  {C.Y}{C.BO}⚠{C.E}  {C.Y}Could not check updates: {e}{C.E}          ")


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
            with open(path, 'r', encoding='utf-8') as f:
                keys = [line.strip() for line in f if line.strip()]
            if not keys:
                print(f"{C.R}No keys in {path}{C.E}")
                sys.exit(1)
            return keys
        except FileNotFoundError:
            print(f"{C.R}{path} not found{C.E}")
            sys.exit(1)

    def key(self) -> str:
        return self.keys[self.idx]

    def rotate(self):
        self.idx = (self.idx + 1) % len(self.keys)
        print(f"{C.Y}  → Switched to key #{self.idx + 1}{C.E}")


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
                print(f"{C.R}  Key ...{km.key()[-6:]} error {code}. Rotating...{C.E}")
                km.rotate()
                attempts += 1
            else:
                print(f"{C.R}  HTTP {code}: {e}{C.E}")
                return None
        except Exception as e:
            print(f"{C.R}  Error: {e}{C.E}")
            return None
    print(f"{C.R}All API keys exhausted.{C.E}")
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

        print(f"  ... fetched {len(all_items)} so far")

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
                key = msvcrt.getch()
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
            print(f"  {C.G}✓{C.E} {title}")
        except Exception as e:
            print(f"  {C.R}✗ {vid}: {e}{C.E}")
    print(f"{C.G}Downloaded {count} thumbnail(s) → {THUMBS_DIR}{C.E}")


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
        print(f"{C.G}Saved {count} link(s) → {OUTPUT_FILE}{C.E}")
    except Exception as e:
        print(f"{C.R}Save error: {e}{C.E}")


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



def _probe_uhd_formats(url: str, cookie_opts: dict) -> list:
    """Return deduplicated descending list of heights >=2160 available for the URL."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return []
    probe_opts = {
        'quiet': True,
        'no_warnings': True,
        'logger': _YtLogger(),
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
    }
    for k, v in cookie_opts.items():
        if not k.startswith('_'):
            probe_opts[k] = v
    try:
        with YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return []
        seen, result = set(), []
        for f in info.get('formats', []):
            h = f.get('height') or 0
            if h >= 2160 and h not in seen:
                seen.add(h)
                result.append(h)
        return sorted(result, reverse=True)
    except Exception:
        return []


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


# Browsers supported by yt-dlp --cookies-from-browser
_BROWSERS = {
    '1': 'chrome',
    '2': 'firefox',
    '3': 'edge',
    '4': 'brave',
    '5': 'opera',
    '6': 'chromium',
}

def _find_chrome_cookie_db() -> str | None:
    """Search for Chrome's cookie DB across all known profile folders."""
    import glob
    local = os.environ.get('LOCALAPPDATA', '')
    patterns = [
        os.path.join(local, 'Google', 'Chrome',       'User Data', '*', 'Network', 'Cookies'),
        os.path.join(local, 'Google', 'Chrome',       'User Data', '*', 'Cookies'),
        os.path.join(local, 'Google', 'Chrome Beta',  'User Data', '*', 'Network', 'Cookies'),
        os.path.join(local, 'Google', 'Chrome SxS',   'User Data', '*', 'Network', 'Cookies'),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            # Prefer 'Default' profile
            for m in matches:
                if 'Default' in m:
                    return m
            return matches[0]
    return None


def _copy_browser_db_to_temp(browser: str) -> str | None:
    """
    Pre-copy Chrome's locked cookie DB using sqlite3 backup (bypasses WAL lock).
    NOTE: Chrome 127+ uses App-Bound Encryption — the DB copy will contain
    encrypted values that cannot be decrypted outside Chrome. In that case
    the copy succeeds but yt-dlp still cannot authenticate.
    Returns path to temp copy, or None if not applicable / not found.
    """
    import sqlite3, shutil, tempfile
    if browser != 'chrome':
        return None

    src = _find_chrome_cookie_db()
    if not src:
        print(f"  {C.Y}Warning: Chrome cookie DB not found under %LOCALAPPDATA%.{C.E}")
        return None

    tmp = tempfile.NamedTemporaryFile(prefix='yt_chrome_cookies_', suffix='.db', delete=False)
    tmp.close()

    # Try sqlite3.backup with immutable flag (reads locked WAL DB without acquiring lock)
    try:
        uri = 'file:{}?mode=ro&nolock=1&immutable=1'.format(src.replace('\\', '/'))
        src_conn = sqlite3.connect(uri, uri=True)
        dst_conn = sqlite3.connect(tmp.name)
        src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        return tmp.name
    except Exception:
        pass

    # Fallback: plain file copy
    try:
        shutil.copy2(src, tmp.name)
        return tmp.name
    except Exception as e:
        print(f"  {C.Y}Warning: could not copy cookie DB — {e}{C.E}")
        if os.path.isfile(tmp.name):
            os.remove(tmp.name)
        return None


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
    '_cookie_mode' = 'none' | 'browser' | 'file' for retry logic.
    """
    _ui_header('Cookies | Authentication', C.Y)
    print(f"  {C.DM}YouTube may block downloads without authentication.{C.E}\n")
    _ui_menu_item('1', 'No cookies', C.CN, 'try without auth')
    _ui_menu_item('2', 'Use cookies from browser', C.CN)
    print(f"      {C.Y}⚠  Chrome 127+ blocks extraction (App-Bound Encryption){C.E}")
    _ui_menu_item('3', 'Use cookies from a .txt file', C.G, '← most reliable')
    print(f"      {C.DM}Export via \'Get cookies.txt LOCALLY\' (Chrome) or \'cookies.txt\' (Firefox){C.E}")
    ch = _ui_prompt()

    if ch == '2':
        print(f"\n  {C.CN}{C.BO}Select browser:{C.E}")
        for k, v in _BROWSERS.items():
            _ui_menu_item(k, v.capitalize(), C.CN)
        bch = _ui_prompt()
        browser = _BROWSERS.get(bch, 'chrome')
        print(f"  {C.G}Will use cookies from: {browser}{C.E}")

        if browser == 'chrome':
            print(f"  {C.Y}⚠  Chrome 127+ uses App-Bound Encryption — this may fail.{C.E}")
            print(f"  {C.Y}   If it does, use Firefox (option 2→2) or cookies.txt (option 3).{C.E}")

        # yt-dlp reads the cookie DB directly — browser must be CLOSED
        print(f"  {C.Y}   Close {browser.capitalize()} completely, then press Enter.{C.E}")
        input("  Press Enter when ready: ")
        return {'cookiesfrombrowser': (browser, None, None, None),
                '_cookie_mode': 'browser', '_browser': browser}

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
        print(f"  {C.G}Metadata saved → {meta_path}{C.E}")
    except Exception as e:
        print(f"  {C.R}Failed to save metadata: {e}{C.E}")


class _YtLogger:
    """Custom logger for yt-dlp: suppresses noise, shows errors and important warnings."""
    _IMPORTANT_WARNINGS = [
        'cookies are no longer valid',
        'cookies have likely been rotated',
        'sign in',
        'no supported javascript',
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


def _progress_hook(d):
    """Styled progress bar for yt-dlp downloads — matches startup bar style."""
    g_dl = '\033[38;5;44m'   # cyan-teal (same as startup)
    g_ok = '\033[38;5;49m'   # green-cyan (done state)

    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed')
        eta = d.get('eta')

        if total > 0:
            pct = downloaded / total
        else:
            pct = 0.0

        bar = _progress_bar_str(pct, 36, g_dl, C.DG)
        pct_str = f"{pct * 100:5.1f}%"
        speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else '?'
        eta_str   = f"{eta}s" if eta else '?'

        spinner = next(_spinner_gen)
        print(f"\r  {g_dl}{spinner}{C.E}  {bar}  {C.DM}{pct_str}{C.E}  {C.DG}{speed_str}  ETA {eta_str}{C.E}   ",
              end='', flush=True)

    elif d['status'] == 'finished':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        size_str = f"{total / 1024 / 1024:.1f} MB" if total else '? MB'
        bar_done = _progress_bar_str(1.0, 36, g_ok)
        print(f"\r  {C.G}{C.BO}✓{C.E}  {bar_done}  {C.DM}100.0%{C.E}  {C.G}{size_str}  Done!{C.E}          ")


def _postprocessor_hook(d):
    """Show clean messages for post-processing steps."""
    g_dl = '\033[38;5;44m'
    g_ok = '\033[38;5;49m'
    if d['status'] == 'started':
        pp = d.get('postprocessor', '')
        if 'Merger' in pp:
            print(f"  {g_dl}⟳{C.E}  {C.W}Merging audio + video...{C.E}")
        elif 'VideoConvertor' in pp or 'VideoRemuxer' in pp:
            print(f"  {g_dl}⟳{C.E}  {C.W}Converting to MP4...{C.E}")
        elif 'ExtractAudio' in pp:
            print(f"  {g_dl}⟳{C.E}  {C.W}Extracting audio (MP3)...{C.E}")
    elif d['status'] == 'finished':
        pp = d.get('postprocessor', '')
        if 'VideoConvertor' in pp or 'VideoRemuxer' in pp:
            print(f"  {C.G}{C.BO}✓{C.E}  {C.G}Converted to MP4{C.E}")
        elif 'FFmpegExtractAudio' in pp:
            print(f"  {C.G}{C.BO}✓{C.E}  {C.G}Audio extracted (MP3){C.E}")
        elif 'Merger' in pp:
            print(f"  {C.G}{C.BO}✓{C.E}  {C.G}Merged successfully{C.E}")


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
        'no_warnings':      False,    # let _YtLogger filter selectively
        'noprogress':       True,
        'logger':           _YtLogger(),
        'progress_hooks':   [_progress_hook],
        'postprocessor_hooks': [_postprocessor_hook],
        # Use Node.js for JS extraction (yt-dlp expects dict format: {runtime: {config}})
        'js_runtimes':      {'node': {}},
        # Download EJS challenge solver from GitHub (required to decrypt YouTube stream URLs)
        'remote_components': ['ejs:github'],
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


def _download_one(ydl, url: str, i: int, total: int, out_dir: str,
                  from_videolinks: bool = False) -> bool:
    """Download a single URL. Returns True on success, False on failure.

    When from_videolinks=True the URL will be removed from videolinks.txt
    after a successful download.
    """
    # Use process=False to get title/basic info WITHOUT running format selection.
    # This avoids format-not-available errors during the info step.
    raw = ydl.extract_info(url, download=False, process=False)
    if not raw:
        print(f"  {C.R}✗  Could not fetch info for {url}{C.E}")
        return False
    title = raw.get('title') or raw.get('id') or url
    _ui_separator()
    print(f"  {C.DG}│{C.E} {C.DM}[{i}/{total}]{C.E}  {C.W}{C.BO}{title}{C.E}")
    print(f"  {C.DG}│{C.E}  {C.DM}→ {out_dir}{C.E}")
    _ui_separator()
    # download() runs the full pipeline: format selection + download + post-process
    ydl.download([url])
    # For metadata, re-fetch with full processing (no download) to get resolved fields
    try:
        info = ydl.extract_info(url, download=False)
        _save_video_metadata(info or raw, out_dir)
    except Exception:
        _save_video_metadata(raw, out_dir)  # use raw info as fallback
    # Remove from videolinks.txt if this batch came from there
    if from_videolinks:
        _remove_url_from_videolinks(url)
        print(f"  {C.G}✓{C.E}  {C.DM}Removed from videolinks.txt{C.E}")
    print()
    return True


def _cleanup_tmp_cookie_db(cookie_opts: dict):
    """Delete the temp cookie DB file if one was created."""
    tmp = cookie_opts.get('_tmp_cookie_db')
    if tmp and os.path.isfile(tmp):
        try:
            os.remove(tmp)
        except Exception:
            pass


_COOKIE_DB_ERROR_SIGNALS = [
    'could not copy',
    'cookie database',
    'database is locked',
    'unable to open database',
]


def _is_cookie_db_error(msg: str) -> bool:
    ml = msg.lower()
    return any(s in ml for s in _COOKIE_DB_ERROR_SIGNALS)


def _print_cookie_db_help(browser: str):
    print(f"\n{C.R}  ✗ Could not read {browser.capitalize()} cookie database.{C.E}")
    print(f"  {C.Y}This usually means the browser is still running.{C.E}")
    print(f"  {C.Y}Solutions:{C.E}")
    print(f"    1. Close ALL {browser.capitalize()} windows completely, then try again.")
    print(f"    2. Export cookies to a .txt file using a browser extension:")
    print(f"       • Chrome/Edge: 'Get cookies.txt LOCALLY' extension")
    print(f"       • Firefox: 'cookies.txt' extension")
    print(f"       Then choose option 3 (cookies from file) in the menu.")
    print(f"    3. Try a different browser (e.g. Firefox or Edge).\n")


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
    browser_name  = cookie_opts.get('_browser', 'chrome')

    # ── Ultra High (4K/8K) mode — probe + resolve format per URL ────────
    if quality_opts.pop('_quality_mode', None) == 'ultra_high':
        uhd_pp = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        failed_urls = []
        try:
            from yt_dlp import YoutubeDL
            for i, url in enumerate(urls, 1):
                # Resolve UHD format for this URL
                while True:
                    print(f"\n{C.CN}[{i}/{len(urls)}] Probing Ultra HD formats...{C.E}")
                    available = _probe_uhd_formats(url, cookie_opts)
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
                            try:
                                _download_one(ydl, url, i, len(urls), out_dir,
                                              from_videolinks=from_videolinks)
                            except Exception as e:
                                err_msg = str(e)
                                if _is_cookie_db_error(err_msg):
                                    _print_cookie_db_help(browser_name)
                                    return
                                print(f"\n{C.R}  Error: {err_msg[:200]}{C.E}")
                                if _is_bot_error(err_msg) and cookie_mode == 'none':
                                    failed_urls.append(url)
                    except Exception as e:
                        print(f"\n{C.R}  Error: {str(e)[:200]}{C.E}")
                    break  # move to next URL
        finally:
            _cleanup_tmp_cookie_db(cookie_opts)
        print(f"  {C.G}{C.BO}✦{C.E}  {C.G}All done → {out_dir}{C.E}")
        return

    base_opts = _build_ydl_opts(out_dir, quality_opts, cookie_opts)

    print(f"\n  {C.G}{C.BO}⬢{C.E}  {C.W}{C.BO}Starting download of {len(urls)} video(s)...{C.E}")
    print(f"  {C.DM}{'─' * 46}{C.E}\n")

    failed_urls = []

    try:
        with YoutubeDL(base_opts) as ydl:
            for i, url in enumerate(urls, 1):
                try:
                    _download_one(ydl, url, i, len(urls), out_dir,
                                  from_videolinks=from_videolinks)
                except Exception as e:
                    err_msg = str(e)

                    # Cookie database locked / copy error
                    if _is_cookie_db_error(err_msg):
                        _print_cookie_db_help(browser_name)
                        break  # no point continuing, all URLs will hit the same error

                    print(f"\n  {C.R}✗  Error: {err_msg[:200]}{C.E}")

                    # If it looks like a bot block and we're not already using cookies
                    if _is_bot_error(err_msg) and cookie_mode == 'none':
                        print(f"  {C.Y}↳ Bot/auth block detected — will retry with browser cookies.{C.E}")
                        failed_urls.append(url)
                    else:
                        print()
    finally:
        _cleanup_tmp_cookie_db(cookie_opts)

    # ── Auto-retry with browser cookies ────────────────────────────────
    if failed_urls:
        _ui_header(f'Retrying {len(failed_urls)} blocked video(s) with browser cookies', C.Y)
        for k, v in _BROWSERS.items():
            _ui_menu_item(k, v.capitalize(), C.CN)
        bch = _ui_prompt()
        browser = _BROWSERS.get(bch, 'chrome')

        # Try to pre-copy the cookie DB before yt-dlp touches it
        tmp_db = _copy_browser_db_to_temp(browser)
        if tmp_db:
            print(f"  {C.G}✓ Cookie DB pre-copied (Chrome snapshot).{C.E}\n")
            retry_cookie_opts = {'cookiefile': tmp_db, '_tmp_cookie_db': tmp_db}
        else:
            print(f"  {C.Y}⚠  Make sure {browser.capitalize()} is fully closed, then press Enter.{C.E}")
            input("  Press Enter when ready: ")
            retry_cookie_opts = {'cookiesfrombrowser': (browser, None, None, None)}

        retry_opts = _build_ydl_opts(out_dir, quality_opts, retry_cookie_opts)

        try:
            with YoutubeDL(retry_opts) as ydl_retry:
                for i, url in enumerate(failed_urls, 1):
                    try:
                        _download_one(ydl_retry, url, i, len(failed_urls), out_dir,
                                      from_videolinks=from_videolinks)
                    except Exception as e:
                        err_msg = str(e)
                        if _is_cookie_db_error(err_msg):
                            _print_cookie_db_help(browser)
                            break
                        print(f"\n  {C.R}✗  Retry failed: {err_msg[:200]}{C.E}\n")
        finally:
            _cleanup_tmp_cookie_db(retry_cookie_opts)

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
                        'remote_components': ['ejs:github']}) as ydl:
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


def _download_thumbnails_for_urls(urls: list, channel_subdir: str):
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

    title_cache = {}  # vid → title
    if YoutubeDL is not None:
        print(f"  {C.CN}Fetching video titles for thumbnails...{C.E}")
        probe_opts = {
            'quiet': True, 'no_warnings': True,
            'logger': _YtLogger(), 'skip_download': True,
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
        }
        try:
            with YoutubeDL(probe_opts) as ydl:
                for url in urls:
                    try:
                        info = ydl.extract_info(url, download=False, process=False)
                        if info:
                            title_cache[info.get('id', '')] = info.get('title', '')
                    except Exception:
                        pass
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


def _parse_download_submenu(urls: list, label: str, channel_subdir: str):
    """
    Inner submenu shown after video-type selection.
    label     — human-readable name, e.g. 'Long videos' or 'Shorts'
    channel_subdir — subfolder name for thumbnails
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
            _download_thumbnails_for_urls(urls, channel_subdir)

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
            _parse_download_submenu(long_urls, 'Long videos', f"{safe_name}_long")
        elif ch == '2':
            if not short_urls:
                print(f"  {C.Y}⚠  No shorts found on this channel.{C.E}")
                continue
            _parse_download_submenu(short_urls, 'Shorts', f"{safe_name}_shorts")
        elif ch == '3':
            all_urls = long_urls + short_urls
            if not all_urls:
                print(f"  {C.Y}⚠  No videos found on this channel.{C.E}")
                continue
            _parse_download_submenu(all_urls, 'Long + Shorts', f"{safe_name}_all")
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
        _ui_menu_item('1', 'Search videos', C.G, '🔍')
        _ui_menu_item('2', 'Download single video by URL', C.CN, '⬇️')
        _ui_menu_item('3', 'Parse channel (long | shorts)', C.H, '📊')
        _ui_menu_item('4', 'Download from videolinks.txt', C.Y, '📥')
        _ui_menu_item('5', 'Download thumbnails', C.B, '🖼️')
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
        elif choice == '0':
            break
        else:
            print(f"  {C.Y}⚠  Invalid choice, try again.{C.E}")

    print(f"\n  {C.G}{C.BO}Goodbye! 👋{C.E}")
    input("  Press Enter to close...")


if __name__ == "__main__":
    main()

