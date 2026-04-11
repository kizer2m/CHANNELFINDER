#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Channel Finder v3.7.1
  Mode 1 — Search videos (filters, thumbnails, channel stats, download)
  Mode 2 — Parse channel (long / shorts classification)
  Mode 3 — Batch download from videolinks.txt (re-encode to MP4 + metadata)
"""

import os
import sys
import re
import json
import subprocess
import urllib.request
import msvcrt
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
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

class C:
    """ANSI colour shortcuts."""
    H  = '\033[95m'
    B  = '\033[94m'
    CN = '\033[96m'
    G  = '\033[92m'
    Y  = '\033[93m'
    R  = '\033[91m'
    BO = '\033[1m'
    E  = '\033[0m'


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
    print(f"{C.CN}Checking for yt-dlp updates...{C.E}")
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            capture_output=True, text=True, timeout=60,
        )
        if 'Successfully installed' in result.stdout:
            print(f"{C.G}yt-dlp updated!{C.E}")
        else:
            print(f"{C.G}yt-dlp is already up to date.{C.E}")
    except Exception as e:
        print(f"{C.Y}Could not check yt-dlp updates: {e}{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  KEY MANAGER
# ═══════════════════════════════════════════════════════════════════════

class KeyManager:
    def __init__(self, path: str):
        self.keys = self._load(path)
        self.idx  = 0
        print(f"{C.G}Loaded {len(self.keys)} API key(s){C.E}")

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
    print(f"\n{C.CN}─── API Key Quota Status ───{C.E}")
    first_valid = None
    for i, api_key in enumerate(km.keys):
        try:
            yt = build('youtube', 'v3', developerKey=api_key)
            yt.search().list(part="id", q="test", maxResults=1).execute()
            status = f"{C.G}✓ Active{C.E}"
            if first_valid is None:
                first_valid = i
        except HttpError as e:
            if e.resp.status in (403, 429):
                status = f"{C.R}✗ Quota exhausted{C.E}"
            elif e.resp.status == 400:
                status = f"{C.R}✗ Invalid key{C.E}"
            else:
                status = f"{C.Y}? HTTP {e.resp.status}{C.E}"
        except Exception as e:
            status = f"{C.Y}? Error: {e}{C.E}"
        print(f"  Key #{i+1} (...{api_key[-6:]}): {status}")
    
    if first_valid is not None:
        km.idx = first_valid
        print(f"{C.G}Using key #{first_valid + 1} as starting key.{C.E}")
    else:
        print(f"{C.R}WARNING: No active keys found! API calls will fail.{C.E}")
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
    print(f"\n{C.CN}─── Filters (Enter to skip) ───{C.E}")

    d = input("  Duration  1=any 2=short(<4m) 3=medium(4-20m) 4=long(>20m) [1]: ").strip()
    duration = {'2': 'short', '3': 'medium', '4': 'long'}.get(d, 'any')

    df = input("  Quality   1=any 2=SD 3=HD [1]: ").strip()
    definition = {'2': 'standard', '3': 'high'}.get(df, 'any')

    print("  Date      1=any 2=hour 3=today 4=week 5=month 6=year")
    ud = input("  Choice [1]: ").strip()
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

    lang = input("  Language code (ru/en/uk/ja/ar/...) []: ").strip() or None

    ps = input("  Results per page (how many to show at a time) [25]: ").strip()
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
        print(f"{C.Y}No results found.{C.E}")
        return

    total = len(results)
    total_pages = (total + page_size - 1) // page_size
    current_page = 0

    print(f"\n{C.G}{C.BO}Found {total} video(s).{C.E}")
    print(f"{C.CN}Showing {page_size} per page ({total_pages} page(s) total).{C.E}")
    print(f"{C.Y}[Space]{C.E} = next page  |  {C.Y}[Escape]{C.E} = stop and go to actions menu\n")

    while current_page < total_pages:
        start = current_page * page_size
        end = min(start + page_size, total)

        for i in range(start, end):
            _print_result_item(i + 1, results[i], ch_stats)

        current_page += 1

        if current_page < total_pages:
            shown = end
            remaining = total - shown
            print(f"{C.BO}── Shown {shown}/{total}  │  Remaining: {remaining}  │  "
                  f"Page {current_page}/{total_pages} ──{C.E}")
            print(f"{C.Y}[Space]{C.E} = show next {min(page_size, remaining)}  |  "
                  f"{C.Y}[Escape]{C.E} = stop\n")

            # Wait for keypress
            while True:
                key = msvcrt.getch()
                if key == b' ':     # Space
                    break
                elif key == b'\x1b':  # Escape
                    print(f"\n{C.CN}Stopped. Shown {shown} of {total} results.{C.E}")
                    return
                # ignore other keys
        else:
            print(f"{C.G}{C.BO}── All {total} result(s) displayed ──{C.E}")


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
    print(f"\n{C.CN}Download quality:{C.E}")
    print("  1 = Best video + audio (re-encode to MP4)")
    print("  2 = 720p max (MP4)")
    print("  3 = 480p max (MP4)")
    print("  4 = Audio only (MP3)")
    q = input("  Choice [1]: ").strip()

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
    else:
        # Full fallback chain: adaptive DASH → any video+audio → combined → anything
        opts['format'] = 'bestvideo+bestaudio/bestvideo*+bestaudio/best/worst'

    # For video modes (not audio-only), re-encode / remux to MP4
    if q != '4':
        opts['merge_output_format'] = 'mp4'
        opts['postprocessors'] = opts.get('postprocessors', []) + [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]

    return opts


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
    print(f"\n{C.CN}─── Cookies / Authentication ───{C.E}")
    print("  YouTube may block downloads without authentication.")
    print(f"  {C.Y}1.{C.E} No cookies (try without authentication)")
    print(f"  {C.Y}2.{C.E} Use cookies from browser")
    print(f"      {C.Y}⚠  Chrome 127+ blocks cookie extraction (App-Bound Encryption).{C.E}")
    print(f"         Use Firefox or Edge, or export via option 3.")
    print(f"  {C.Y}3.{C.E} Use cookies from a .txt file {C.G}← most reliable{C.E}")
    print(f"      Export via 'Get cookies.txt LOCALLY' (Chrome/Edge) or 'cookies.txt' (Firefox)")
    ch = input(f"  Choice [1]: ").strip()

    if ch == '2':
        print(f"\n  {C.CN}Select browser:{C.E}")
        for k, v in _BROWSERS.items():
            print(f"    {k}. {v.capitalize()}")
        bch = input("    Choice [1]: ").strip()
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
        print(f"\n  {C.CN}Cookie file selection:{C.E}")
        print(f"  {C.Y}[Enter]{C.E} — scan current script folder for cookies.txt automatically")
        print(f"  {C.Y}[Path] {C.E} — type a custom path to a file or folder, then press Enter")
        raw = input("  Path (or Enter to scan script folder): ").strip().strip('"')

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
    """Green progress bar for yt-dlp downloads."""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed')
        eta = d.get('eta')

        if total > 0:
            pct = downloaded / total
            bar_len = 40
            filled = int(bar_len * pct)
            bar = '█' * filled + '░' * (bar_len - filled)
            pct_str = f"{pct * 100:5.1f}%"
        else:
            bar = '░' * 40
            pct_str = '  ?%'

        speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else '? MB/s'
        eta_str = f"{eta}s" if eta else '?'

        print(f"\r  {C.G}{bar}{C.E} {pct_str}  {speed_str}  ETA {eta_str}   ", end='', flush=True)

    elif d['status'] == 'finished':
        filename = d.get('filename', '')
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        size_str = f"{total / 1024 / 1024:.1f} MB" if total else '? MB'
        print(f"\r  {C.G}{'█' * 40}{C.E} 100.0%  {size_str}  Done!")


def _postprocessor_hook(d):
    """Show clean messages for post-processing steps."""
    if d['status'] == 'started':
        pp = d.get('postprocessor', '')
        if 'Merger' in pp:
            print(f"  {C.CN}Merging audio + video...{C.E}")
        elif 'VideoConvertor' in pp or 'VideoRemuxer' in pp:
            print(f"  {C.CN}Converting to MP4...{C.E}")
        elif 'ExtractAudio' in pp:
            print(f"  {C.CN}Extracting audio (MP3)...{C.E}")
    elif d['status'] == 'finished':
        pp = d.get('postprocessor', '')
        if 'VideoConvertor' in pp or 'VideoRemuxer' in pp:
            print(f"  {C.G}✓ Converted to MP4{C.E}")


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
        print(f"{C.R}  Could not fetch info for {url}{C.E}")
        return False
    title = raw.get('title') or raw.get('id') or url
    print(f"{C.BO}[{i}/{total}]{C.E} {C.CN}{title}{C.E}")
    print(f"  → {out_dir}")
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
        print(f"  {C.G}✓ Removed from videolinks.txt{C.E}")
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

    base_opts = _build_ydl_opts(out_dir, quality_opts, cookie_opts)

    print(f"\n{C.G}Starting download of {len(urls)} video(s)...{C.E}\n")

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

                    print(f"\n{C.R}  Error: {err_msg[:200]}{C.E}")

                    # If it looks like a bot block and we're not already using cookies
                    if _is_bot_error(err_msg) and cookie_mode == 'none':
                        print(f"{C.Y}  ↳ Bot/auth block detected — will retry with browser cookies.{C.E}")
                        failed_urls.append(url)
                    else:
                        print()
    finally:
        _cleanup_tmp_cookie_db(cookie_opts)

    # ── Auto-retry with browser cookies ────────────────────────────────
    if failed_urls:
        print(f"\n{C.Y}─── Retrying {len(failed_urls)} blocked video(s) with browser cookies ───{C.E}")
        print(f"  {C.CN}Select browser for cookies:{C.E}")
        for k, v in _BROWSERS.items():
            print(f"    {k}. {v.capitalize()}")
        bch = input("    Choice [1 = Chrome]: ").strip()
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
                        print(f"\n{C.R}  Retry failed: {err_msg[:200]}{C.E}\n")
        finally:
            _cleanup_tmp_cookie_db(retry_cookie_opts)

    print(f"{C.G}All done → {out_dir}{C.E}")


def download_selected(results: list):
    """Let user pick which search results to download."""
    try:
        from yt_dlp import YoutubeDL  # noqa: F401
    except ImportError:
        print(f"{C.R}yt-dlp not installed. pip install yt-dlp{C.E}")
        return

    items = [r for r in results if r['id'].get('videoId')]
    if not items:
        print("No downloadable videos.")
        return

    print(f"\n{C.CN}Enter numbers (e.g. 1,3,5) or 'all':{C.E}")
    ch = input("  > ").strip().lower()
    if ch == 'all':
        sel = items
    else:
        try:
            idxs = [int(x.strip()) - 1 for x in ch.split(',')]
            sel = [items[i] for i in idxs if 0 <= i < len(items)]
        except (ValueError, IndexError):
            print(f"{C.R}Invalid input.{C.E}")
            return
    if not sel:
        print("Nothing selected.")
        return

    urls = [f"https://www.youtube.com/watch?v={it['id']['videoId']}" for it in sel]
    _download_urls(urls, DOWNLOADS_DIR)


def search_post_menu(results: list, query: str, km: KeyManager, page_size: int = 25) -> str:
    """After-search actions. Returns 'search' to loop, 'menu' to go back."""
    while True:
        print(f"\n{C.BO}─── Actions ({len(results)} result(s) loaded) ───{C.E}")
        print("  1. Save ALL results → find.txt")
        print("  2. Show results again (paginated)")
        print("  3. Download thumbnails (max resolution)")
        print("  4. Download videos (yt-dlp → MP4)")
        print("  5. Show channel analytics")
        print("  6. New search")
        print("  0. Back to main menu")
        ch = input(f"{C.CN}  > {C.E}").strip()

        if ch == '1':
            print(f"{C.CN}Saving all {len(results)} result(s) to find.txt...{C.E}")
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
                print(f"\n{C.BO}Channel Analytics:{C.E}")
                for cid, s in stats.items():
                    print(f"  {C.CN}{s['title']}{C.E}  "
                          f"Subs: {s['subs']}  Videos: {s['vids']}  Views: {s['views']}")
            else:
                print(f"{C.Y}Could not load channel stats.{C.E}")
        elif ch == '6':
            return 'search'
        elif ch == '0':
            return 'menu'


def mode_search(km: KeyManager):
    """Search mode loop."""
    while True:
        query = input(f"\n{C.BO}Search query (or 'back'): {C.E}").strip()
        if query.lower() in ('back', 'exit', 'quit'):
            return
        if not query:
            continue

        filters = ask_filters()
        page_size = filters.get('page_size', 25)

        print(f"\n{C.G}Searching for '{query}'...{C.E}")
        results = search_youtube_all(km, query, filters)

        if not results:
            print(f"{C.Y}No results found.{C.E}")
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
      @handle
    Returns (channel_id, channel_title) or (None, None).
    """
    user_input = user_input.strip()

    # Direct channel URL
    m = re.search(r'youtube\.com/channel/(UC[\w-]+)', user_input)
    if m:
        cid = m.group(1)
        resp = api_call(km, lambda yt: yt.channels().list(part="snippet", id=cid))
        if resp and resp.get('items'):
            return cid, resp['items'][0]['snippet']['title']
        return cid, cid

    # @handle (in URL or standalone)
    m = re.search(r'@([\w.\-]+)', user_input)
    if m:
        handle = m.group(0)  # includes @
        # Try forHandle first (YouTube API v3 supports it on channels().list)
        resp = api_call(km, lambda yt: yt.channels().list(
            part="snippet", forHandle=handle.lstrip('@')))
        if resp and resp.get('items'):
            it = resp['items'][0]
            return it['id'], it['snippet']['title']
        # Fallback: search
        resp = api_call(km, lambda yt: yt.search().list(
            part="snippet", q=handle, type="channel", maxResults=1))
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


def mode_parse(km: KeyManager):
    """Channel parsing mode."""
    print(f"\n{C.BO}─── Channel Parser ───{C.E}")
    print("Paste a channel URL or @handle (e.g. @MrBeast)")
    user_in = input(f"{C.CN}  Channel: {C.E}").strip()
    if not user_in:
        return

    print(f"{C.G}Resolving channel...{C.E}")
    cid, ctitle = resolve_channel_id(km, user_in)
    if not cid:
        print(f"{C.R}Channel not found.{C.E}")
        return

    print(f"{C.G}Channel: {ctitle}  ({cid}){C.E}")
    print(f"{C.CN}Fetching all videos (may take a while)...{C.E}")

    all_vids = fetch_all_channel_videos(km, cid)
    if not all_vids:
        print(f"{C.Y}No videos found.{C.E}")
        return

    print(f"\n{C.G}Total videos fetched: {len(all_vids)}{C.E}")
    print(f"{C.CN}Classifying long vs. shorts...{C.E}")

    longs, shorts = classify_videos(km, all_vids)

    print(f"\n{C.BO}Results for {C.CN}{ctitle}{C.E}{C.BO}:{C.E}")
    print(f"  {C.G}Long videos (>60 s):  {len(longs)}{C.E}")
    print(f"  {C.Y}Shorts     (≤60 s):  {len(shorts)}{C.E}")

    # Save to parsed/
    os.makedirs(PARSED_DIR, exist_ok=True)
    safe_name = safe_filename(ctitle)

    long_path  = os.path.join(PARSED_DIR, f"{safe_name}_long.txt")
    short_path = os.path.join(PARSED_DIR, f"{safe_name}_shorts.txt")

    with open(long_path, 'w', encoding='utf-8') as f:
        for v in longs:
            f.write(f"https://www.youtube.com/watch?v={v['videoId']}\n")

    with open(short_path, 'w', encoding='utf-8') as f:
        for v in shorts:
            f.write(f"https://www.youtube.com/watch?v={v['videoId']}\n")

    print(f"{C.G}Saved → {long_path}{C.E}")
    print(f"{C.G}Saved → {short_path}{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  MODE 3 — BATCH DOWNLOAD FROM videolinks.txt
# ═══════════════════════════════════════════════════════════════════════

def mode_download():
    """Read URLs from videolinks.txt and download them all."""
    if not os.path.exists(VIDEOLINKS):
        print(f"{C.R}File not found: {VIDEOLINKS}{C.E}")
        print(f"Create it and put one YouTube URL per line.")
        # Create an empty template
        with open(VIDEOLINKS, 'w', encoding='utf-8') as f:
            f.write("# Put one YouTube video URL per line\n")
        print(f"{C.Y}Created empty template → {VIDEOLINKS}{C.E}")
        return

    with open(VIDEOLINKS, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f
                if line.strip() and not line.strip().startswith('#')]

    if not urls:
        print(f"{C.Y}No URLs in {VIDEOLINKS}{C.E}")
        return

    print(f"\n{C.G}Found {len(urls)} URL(s) in videolinks.txt:{C.E}")
    for i, u in enumerate(urls, 1):
        print(f"  {i}. {u}")

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
    url = input(f"\n{C.BO}Paste video URL: {C.E}").strip()
    if not url:
        return

    # Extract video ID
    m = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url)
    if not m:
        print(f"{C.R}Could not extract video ID from URL.{C.E}")
        return
    vid = m.group(1)

    # Get title via API
    resp = api_call(km, lambda yt: yt.videos().list(part="snippet", id=vid))
    if resp and resp.get('items'):
        title = resp['items'][0]['snippet']['title']
    else:
        title = vid

    print(f"{C.CN}Downloading thumbnail for: {title}{C.E}")
    _download_single_thumbnail(vid, title)
    print(f"{C.G}Done → {THUMBS_DIR}{C.E}")


def thumb_channel(km: KeyManager):
    """Download all thumbnails from a channel."""
    user_in = input(f"\n{C.BO}Paste channel URL or @handle: {C.E}").strip()
    if not user_in:
        return

    print(f"{C.G}Resolving channel...{C.E}")
    cid, ctitle = resolve_channel_id(km, user_in)
    if not cid:
        print(f"{C.R}Channel not found.{C.E}")
        return

    print(f"{C.G}Channel: {ctitle}{C.E}")
    print(f"{C.CN}Fetching videos...{C.E}")

    all_vids = fetch_all_channel_videos(km, cid)
    if not all_vids:
        print(f"{C.Y}No videos found.{C.E}")
        return

    print(f"{C.G}Found {len(all_vids)} video(s). Downloading thumbnails...{C.E}")
    os.makedirs(THUMBS_DIR, exist_ok=True)

    count = 0
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
            print(f"  {C.G}✓{C.E} {title}")
        except Exception as e:
            print(f"  {C.R}✗ {vid}: {e}{C.E}")

    print(f"\n{C.G}Downloaded {count} thumbnail(s) → {THUMBS_DIR}{C.E}")


def mode_thumbnails(km: KeyManager):
    """Thumbnail download menu."""
    print(f"\n{C.BO}─── Thumbnails ───{C.E}")
    print(f"  {C.CN}1.{C.E} Download from single video URL")
    print(f"  {C.CN}2.{C.E} Download all from a channel")
    print(f"  {C.CN}0.{C.E} Back")
    ch = input(f"{C.CN}  > {C.E}").strip()

    if ch == '1':
        thumb_single(km)
    elif ch == '2':
        thumb_channel(km)


# ═══════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════════

def main():
    os.system('')  # enable ANSI colours on Windows

    print(f"{C.BO}{C.H}")
    print("╔══════════════════════════════════════════════╗")
    print("║       YouTube Channel Finder  v3.7.1         ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"{C.E}")

    check_updates()
    km = KeyManager(API_KEYS_FILE)
    check_key_quotas(km)

    while True:
        print(f"\n{C.BO}═══ Main Menu ═══{C.E}")
        print(f"  {C.CN}1.{C.E} Search videos")
        print(f"  {C.CN}2.{C.E} Parse channel (long / shorts)")
        print(f"  {C.CN}3.{C.E} Download from videolinks.txt")
        print(f"  {C.CN}4.{C.E} Download thumbnails")
        print(f"  {C.CN}0.{C.E} Exit")

        choice = input(f"{C.CN}  > {C.E}").strip()

        if choice == '1':
            mode_search(km)
        elif choice == '2':
            mode_parse(km)
        elif choice == '3':
            mode_download()
        elif choice == '4':
            mode_thumbnails(km)
        elif choice == '0':
            break
        else:
            print(f"{C.Y}Invalid choice, try again.{C.E}")

    print(f"\n{C.G}Goodbye!{C.E}")
    input("Press Enter to close...")


if __name__ == "__main__":
    main()

