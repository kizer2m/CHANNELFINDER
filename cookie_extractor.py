#!/usr/bin/env python3
"""
Cookie Extractor for YouTube Channel Finder
===========================================
Exports fresh YouTube cookies to cookies.txt (Netscape format, read by yt-dlp).

Why a dedicated browser profile:
  - Chrome 127+ / Edge encrypt cookies with App-Bound Encryption, so nothing
    outside the browser (incl. yt-dlp --cookies-from-browser) can decrypt them.
  - The browser itself can: we launch Chrome/Edge with a separate profile kept in
    ./browser_profile/, ask it for the cookies over the DevTools protocol and close it.
  - Your main browser is never touched and may stay open.
  - The profile is only opened by this tool, so YouTube does not rotate the
    exported session behind our back (the usual reason cookies.txt "expires").

Usage:
  extract_cookies.cmd                 interactive menu
  python cookie_extractor.py --refresh   non-interactive refresh (exit code 0 = ok)
"""

import os
import sys
import json
import time
import shutil
import socket
import platform
import subprocess
import urllib.request

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(SCRIPT_DIR, 'cookies.txt')
PROFILE_ROOT = os.path.join(SCRIPT_DIR, 'browser_profile')

_LOGIN_URL = ('https://accounts.google.com/ServiceLogin?service=youtube'
              '&continue=https%3A%2F%2Fwww.youtube.com%2F')
_YT_URL = 'https://www.youtube.com/'
# Present only when a Google account is signed in on youtube.com
_LOGIN_COOKIES = ('SAPISID', '__Secure-3PAPISID', 'LOGIN_INFO')


class C:
    """ANSI colour shortcuts (same palette as youtube_finder.py)."""
    CN = '\033[96m'
    G  = '\033[92m'
    Y  = '\033[93m'
    R  = '\033[91m'
    BO = '\033[1m'
    DM = '\033[2m'
    W  = '\033[97m'
    DG = '\033[90m'
    E  = '\033[0m'


# ═══════════════════════════════════════════════════════════════════════
#  BROWSER DISCOVERY
# ═══════════════════════════════════════════════════════════════════════

def _browser_candidates(name: str) -> list:
    system = platform.system()
    if system == 'Windows':
        roots = [os.environ.get(v, '') for v in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')]
        rel = {'chrome': os.path.join('Google', 'Chrome', 'Application', 'chrome.exe'),
               'edge':   os.path.join('Microsoft', 'Edge', 'Application', 'msedge.exe')}[name]
        return [os.path.join(r, rel) for r in roots if r]
    if system == 'Darwin':
        return [{'chrome': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                 'edge':   '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'}[name]]
    cmds = {'chrome': ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'],
            'edge':   ['microsoft-edge', 'microsoft-edge-stable']}[name]
    return [p for p in (shutil.which(c) for c in cmds) if p]


def find_browser() -> tuple:
    """Return (name, exe_path) of the first installed Chromium browser, or (None, None)."""
    for name in ('chrome', 'edge'):
        for path in _browser_candidates(name):
            if path and os.path.isfile(path):
                return name, path
    return None, None


def profile_dir(browser: str) -> str:
    return os.path.join(PROFILE_ROOT, browser)


def has_profile(browser: str = None) -> bool:
    """True if the dedicated profile was already created (= user went through login once)."""
    if browser is None:
        browser, _ = find_browser()
    return bool(browser) and os.path.isdir(os.path.join(profile_dir(browser), 'Default'))


# ═══════════════════════════════════════════════════════════════════════
#  DEVTOOLS PROTOCOL
# ═══════════════════════════════════════════════════════════════════════

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _http_json(url: str, method: str = 'GET', timeout: float = 2.0):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


class _CDP:
    """Minimal synchronous DevTools client over websocket-client."""

    def __init__(self, ws_url: str):
        import websocket  # websocket-client
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.next_id = 0

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        msg_id = self.next_id
        self.ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == msg_id:
                if 'error' in msg:
                    raise RuntimeError(f"{method}: {msg['error'].get('message')}")
                return msg.get('result', {})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def _launch(exe: str, browser: str, extra_args: list) -> subprocess.Popen:
    args = [exe,
            f'--user-data-dir={profile_dir(browser)}',
            '--no-first-run', '--no-default-browser-check',
            '--disable-sync'] + extra_args
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags)


def _stop(proc: subprocess.Popen, browser_cdp: '_CDP' = None):
    if browser_cdp is not None:
        try:
            browser_cdp.call('Browser.close')
        except Exception:
            pass
        browser_cdp.close()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# ═══════════════════════════════════════════════════════════════════════
#  COOKIES.TXT WRITER
# ═══════════════════════════════════════════════════════════════════════

def _is_youtube_domain(domain: str) -> bool:
    d = domain.lstrip('.').lower()
    return d == 'youtube.com' or d.endswith('.youtube.com')


def write_netscape(cookies: list, out_file: str):
    """cookies: dicts with domain, path, secure, expires, name, value. Atomic write."""
    lines = ['# Netscape HTTP Cookie File',
             '# Generated by cookie_extractor.py — do not share, contains your login session',
             '']
    for c in cookies:
        domain = c['domain']
        expires = int(c.get('expires') or 0)
        lines.append('\t'.join([
            domain,
            'TRUE' if domain.startswith('.') else 'FALSE',
            c.get('path') or '/',
            'TRUE' if c.get('secure') else 'FALSE',
            str(max(expires, 0)),
            c['name'],
            c['value'],
        ]))
    tmp = out_file + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(tmp, out_file)


# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC API (used by youtube_finder.py)
# ═══════════════════════════════════════════════════════════════════════

def login(log=print) -> bool:
    """Open a visible browser window on the dedicated profile so the user can sign in.

    Started WITHOUT the DevTools port: Google refuses sign-in in browsers it
    considers automated. Blocks until the user closes the window.
    """
    browser, exe = find_browser()
    if not exe:
        log(f"  {C.R}✗  Neither Google Chrome nor Microsoft Edge was found.{C.E}")
        return False
    os.makedirs(profile_dir(browser), exist_ok=True)
    log(f"\n  {C.CN}{C.BO}A separate {browser.capitalize()} window will open (tool profile).{C.E}")
    log(f"  {C.W}1.{C.E} Sign in to Google / YouTube {C.DM}(a secondary account is recommended){C.E}")
    log(f"  {C.W}2.{C.E} Make sure youtube.com shows you as signed in")
    log(f"  {C.W}3.{C.E} {C.BO}Close that window{C.E} — extraction continues automatically\n")
    proc = _launch(exe, browser, ['--new-window', _LOGIN_URL])
    proc.wait()
    return True


def refresh(out_file: str = COOKIES_FILE, log=print) -> tuple:
    """Open the tool profile headless, load youtube.com, export its cookies.

    Returns (ok: bool, message: str, logged_in: bool).
    """
    try:
        import websocket  # noqa: F401
    except ImportError:
        return False, 'websocket-client is not installed (pip install websocket-client)', False

    browser, exe = find_browser()
    if not exe:
        return False, 'Neither Google Chrome nor Microsoft Edge was found', False
    if not has_profile(browser):
        return False, 'Tool browser profile not set up yet — log in first', False

    port = _free_port()
    proc = _launch(exe, browser, [f'--remote-debugging-port={port}',
                                  '--remote-allow-origins=*',
                                  '--headless=new', 'about:blank'])
    browser_cdp = None
    try:
        # Wait for DevTools endpoint
        version = None
        for _ in range(60):
            if proc.poll() is not None:
                return False, ('Browser exited immediately — is the tool profile open in '
                               'another window? Close it and retry'), False
            try:
                version = _http_json(f'http://127.0.0.1:{port}/json/version')
                break
            except Exception:
                time.sleep(0.25)
        if not version:
            return False, 'Browser DevTools endpoint did not start', False

        browser_cdp = _CDP(version['webSocketDebuggerUrl'])
        target = _http_json(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT')
        page = _CDP(target['webSocketDebuggerUrl'])
        try:
            # Headless Chrome announces itself as "HeadlessChrome" — look like a normal browser
            ua = version.get('User-Agent', '').replace('HeadlessChrome', 'Chrome')
            if ua:
                page.call('Network.setUserAgentOverride', userAgent=ua)
            page.call('Page.enable')
            log(f"  {C.CN}⟳  Opening youtube.com in tool profile ({browser})...{C.E}")
            page.call('Page.navigate', url=_YT_URL)
            # Let the page load and refresh rotating session cookies (__Secure-*PSIDTS)
            deadline = time.time() + 20
            while time.time() < deadline:
                state = page.call('Runtime.evaluate', expression='document.readyState',
                                  returnByValue=True)
                if state.get('result', {}).get('value') == 'complete':
                    break
                time.sleep(0.5)
            time.sleep(4)
        finally:
            page.close()

        all_cookies = browser_cdp.call('Storage.getCookies').get('cookies', [])
        yt = [c for c in all_cookies if _is_youtube_domain(c.get('domain', ''))]
        if not yt:
            return False, 'No youtube.com cookies received from the browser', False

        logged_in = any(c['name'] in _LOGIN_COOKIES for c in yt)
        write_netscape(yt, out_file)
        msg = f'{len(yt)} cookies saved → {out_file}'
        return True, msg, logged_in
    except Exception as e:
        return False, f'Extraction failed: {e}', False
    finally:
        _stop(proc, browser_cdp)


def import_from_browser(browser: str, out_file: str = COOKIES_FILE) -> tuple:
    """Fallback: read cookies from an installed browser via yt-dlp (works for Firefox;
    Chrome 127+/Edge usually fail because of App-Bound Encryption).
    Returns (ok, message, logged_in)."""
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
    except ImportError:
        return False, 'yt-dlp is not installed', False
    try:
        jar = extract_cookies_from_browser(browser)
    except Exception as e:
        return False, f'{browser}: {e}', False
    yt = [{'domain': c.domain, 'path': c.path, 'secure': c.secure,
           'expires': c.expires, 'name': c.name, 'value': c.value or ''}
          for c in jar if _is_youtube_domain(c.domain)]
    if not yt:
        return False, f'No youtube.com cookies found in {browser}', False
    logged_in = any(c['name'] in _LOGIN_COOKIES for c in yt)
    write_netscape(yt, out_file)
    return True, f'{len(yt)} cookies saved → {out_file}', logged_in


def ensure_cookies(out_file: str = COOKIES_FILE, log=print, ask=input) -> bool:
    """Refresh cookies from the tool profile; run the login flow first if needed."""
    if not has_profile():
        log(f"  {C.Y}Tool browser profile is not set up yet — one-time sign-in needed.{C.E}")
        if not login(log):
            return False
    ok, msg, logged_in = refresh(out_file, log)
    if ok and not logged_in:
        log(f"  {C.Y}⚠  Not signed in to YouTube in the tool profile.{C.E}")
        ans = ask(f"  Open the sign-in window now? [Y/n]: ").strip().lower()
        if ans in ('', 'y', 'yes', 'д', 'да'):
            login(log)
            ok, msg, logged_in = refresh(out_file, log)
    _report(ok, msg, logged_in, log)
    return ok and logged_in


def _report(ok: bool, msg: str, logged_in: bool, log=print):
    if not ok:
        log(f"  {C.R}✗  {msg}{C.E}")
        return
    log(f"  {C.G}✓  {msg}{C.E}")
    if logged_in:
        log(f"  {C.G}✓  Signed-in YouTube session{C.E}")
    else:
        log(f"  {C.Y}⚠  Guest cookies only (not signed in) — limited benefit{C.E}")


# ═══════════════════════════════════════════════════════════════════════
#  STANDALONE MENU
# ═══════════════════════════════════════════════════════════════════════

def _menu():
    os.system('')  # enable ANSI colours on Windows
    browser, exe = find_browser()
    while True:
        print(f"\n  {C.CN}{C.BO}─── YouTube Cookie Extractor ───────────────────{C.E}")
        print(f"  {C.DG}│{C.E} {C.DM}Output : {COOKIES_FILE}{C.E}")
        print(f"  {C.DG}│{C.E} {C.DM}Browser: {exe or 'Chrome/Edge not found'}{C.E}")
        state = f"{C.G}ready{C.E}" if has_profile(browser) else f"{C.Y}not set up (sign in first){C.E}"
        print(f"  {C.DG}│{C.E} {C.DM}Profile:{C.E} {state}\n")
        print(f"  {C.DG}│{C.E} {C.W}{C.BO}1.{C.E} Refresh cookies.txt  {C.DM}(tool profile, invisible){C.E}")
        print(f"  {C.DG}│{C.E} {C.W}{C.BO}2.{C.E} Sign in / switch account  {C.DM}(opens browser window){C.E}")
        print(f"  {C.DG}│{C.E} {C.W}{C.BO}3.{C.E} Import from Firefox  {C.DM}(via yt-dlp){C.E}")
        print(f"  {C.DG}│{C.E} {C.DG}0. Exit{C.E}")
        ch = input(f"  {C.CN}›{C.E} ").strip()
        if ch == '1':
            ensure_cookies()
        elif ch == '2':
            if login():
                _report(*refresh())
        elif ch == '3':
            _report(*import_from_browser('firefox'))
        elif ch == '0':
            return


if __name__ == '__main__':
    if '--refresh' in sys.argv:
        os.system('')
        ok, msg, logged_in = refresh()
        _report(ok, msg, logged_in)
        sys.exit(0 if ok else 1)
    _menu()
