# YouTube Channel Finder v3.8.0

A powerful command-line tool for searching YouTube videos, parsing channels, downloading videos, and grabbing thumbnails — all powered by the YouTube Data API v3 with automatic API key rotation.

---

## Features

### 🔍 Mode 1 — Search Videos
- Search YouTube by keywords with advanced filters:
  - **Duration**: any / short (<4 min) / medium (4–20 min) / long (>20 min)
  - **Quality**: any / SD / HD
  - **Date range**: last hour / today / week / month / year
  - **Language**: filter by relevance language code (e.g. `ru`, `en`, `ja`)
  - **Results per page**: how many results to show at a time (1–50, default 25)
- **Full search**: fetches ALL available results via API pagination (not limited to 25)
- **Paginated display**: results shown in batches; press `[Space]` for next page, `[Escape]` to stop
- Displays total results count and current page progress
- Displays results with channel analytics (subscribers, total views, video count)
- **Post-search actions**:
  - Save ALL video links to `find.txt` (URLs only, one per line)
  - Re-display results (paginated)
  - Download max-resolution thumbnails
  - Download selected videos as MP4 with quality selection
  - View detailed channel analytics

### 🔹 Mode 2 — Download Single Video by URL
- Paste any YouTube video URL and get **instant statistics** before deciding what to do:
  - Title, channel, upload date, duration
  - View count, like count, comment count
  - Resolution, FPS, categories, tags
- After displaying stats, choose from a sub-menu:
  1. **Download video** — full quality/cookie/proxy selection (same options as Mode 4)
     - Downloads video as MP4 (or MP3 for audio) and **saves metadata to a `.txt` file**
  2. **Download thumbnail** — downloads the max-resolution thumbnail to `thumbnails/`
- Fetches stats via yt-dlp (no API quota used)

### 📋 Mode 3 — Parse Channel
- Accepts channel URL, `@handle`, or free-text search
- Fetches **all** videos from a channel using the **uploads playlist** (`playlistItems` API)
  - No result cap — works correctly even for channels with **thousands** of videos
  - Uses only **1 quota unit** per API call (100× cheaper than search)
- Classifies videos into **Long** (>60s) and **Shorts** (≤60s)
- Saves results to `parsed/` folder as separate files with links only:
  - `ChannelName_long.txt`
  - `ChannelName_shorts.txt`

### ⬇️ Mode 4 — Batch Download
- Reads video URLs from `videolinks.txt` (one URL per line)
- **Quality selection**: Best / 720p / 480p / Audio-only (MP3)
- Re-encodes to MP4 automatically via FFmpeg
- **🍪 Cookie / Authentication support**:
  - Choose how to handle YouTube authentication before every download:
    - **No cookies** — try without authentication first
    - **Browser cookies** — extract cookies from Firefox, Edge, Brave, Opera, or Chromium (Chrome 127+ may fail due to App-Bound Encryption)
    - **Cookies file** — supply a Netscape-format `cookies.txt` file:
      - Press `[Enter]` to auto-scan the script folder for `cookies.txt` automatically
      - Or type a custom path to a file or folder — the script auto-detects `cookies.txt`, `www.youtube.com_cookies.txt`, `youtube_cookies.txt`
      - **Cookie validation**: the tool tests cookies against YouTube before starting any download. If cookies are expired or invalid, an error is shown immediately
  - If downloading fails due to a bot-detection block, the tool automatically retries blocked videos with browser cookies
- **Auto-remove completed URLs**: each URL is removed from `videolinks.txt` immediately after a successful download, so interrupted sessions resume cleanly from where they left off
- **JavaScript challenge solver** — uses Node.js + EJS remote component to decrypt YouTube stream URLs (required since 2025; without it only storyboard thumbnails are available)
- **Clean download UI**:
  - Green progress bar with speed and ETA
  - Shows only actionable warnings (cookie expiry, JS runtime issues)
  - Critical errors always shown
- Saves full video metadata to a `.txt` file per video (title, channel, views, likes, tags, description, etc.)
- Handles duplicate titles by appending `[videoId]` to filenames

### 🖼️ Mode 5 — Download Thumbnails
- **Single video**: paste a video URL → downloads max-resolution thumbnail
- **Entire channel**: paste a channel URL or `@handle` → downloads all video thumbnails
- Thumbnails saved as `Title [videoId].jpg` (max-res with fallback to HQ)
- All saved to `thumbnails/` folder

### 🔑 API Key Management
- Keys stored in `api_keys.txt` (one per line)
- On startup, each key is tested and status displayed:
  - ✓ Active
  - ✗ Quota exhausted
  - ✗ Invalid key
- Auto-rotation: if a key's quota runs out mid-operation, the script switches to the next available key seamlessly
- First valid key is selected automatically as the starting key

### 🔄 Auto-Update
- Checks for `yt-dlp` updates on every launch and upgrades automatically

---

## Installation

### Prerequisites

- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — required for video merging and MP4 conversion
  - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - Add to system PATH
- **Node.js** — **required** for YouTube JS challenge solving (stream URL decryption)
  - Download from [nodejs.org](https://nodejs.org/)
  - Add to system PATH

### Setup

1. **Clone or download** the project folder

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   This installs:
   - `google-api-python-client` — YouTube Data API
   - `yt-dlp` — video downloading

3. **Add your API keys** to `api_keys.txt` (one key per line):
   ```
   AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   AIzaSyYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
   ```

4. **Run the script**:
   ```bash
   python youtube_finder.py
   ```
   Or use the launcher:
   ```bash
   run_search.cmd
   ```

---

## Fixing "Sign in to confirm you're not a bot"

YouTube increasingly blocks anonymous downloads. The tool handles this in two ways:

### Option A — Let the tool auto-retry (easiest)
1. When the cookie prompt appears, pick **1 (No cookies)** and start the download
2. If a video is blocked, the tool will print:
   ```
   ↳ Bot/auth block detected — will retry with browser cookies.
   ```
3. After the batch finishes you'll be asked which browser to use for the retry — that's it

### Option B — Use a cookies.txt file (most reliable)
1. Export cookies from your browser using an extension:  
   *"Get cookies.txt LOCALLY"* (Chrome/Edge) or *"cookies.txt"* (Firefox)
2. When the cookie prompt appears, pick **3 (Cookies from file)**
3. Press `[Enter]` to auto-scan the script folder, **or** enter a custom path to the `.txt` file or a folder containing it
4. The tool **validates** the cookies before starting — if they are expired you'll see a clear error message so you know to re-export

> ⚠️ **Chrome rotates session tokens** every few hours as a security measure.  
> If "Sign in to confirm" reappears, simply re-export fresh cookies.

### Option C — Browser cookies
1. When the cookie prompt appears, pick **2 (Use cookies from browser)**
2. Select your browser (Firefox / Edge / Brave / Opera / Chromium)
3. Make sure you are **logged into YouTube** in that browser and the browser is **fully closed**

> ⚠️ **Chrome 127+** uses App-Bound Encryption — cookie extraction will likely fail.  
> Use Firefox or Edge instead, or export a `cookies.txt` file (Option B).

---

## How to Get a YouTube Data API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services** → **Library**
4. Search for **YouTube Data API v3** and click **Enable**
5. Go to **APIs & Services** → **Credentials**
6. Click **+ CREATE CREDENTIALS** → **API key**
7. Copy the generated key
8. *(Optional)* Click **Edit API key** to restrict it to YouTube Data API v3 only
9. Paste the key into `api_keys.txt`

> **Tip:** Each API key has a daily quota of **10,000 units**. A single search costs ~100 units, while channel parsing uses only ~1 unit per page (50 videos). Add multiple keys to extend your daily capacity — the script rotates through them automatically.

---

## Project Structure

```
CHANNELFINDER/
├── youtube_finder.py    # Main script
├── api_keys.txt         # API keys (one per line)
├── requirements.txt     # Python dependencies
├── run_search.cmd       # Windows launcher
├── videolinks.txt       # URLs for batch download (Mode 3)
├── find.txt             # Saved search results (links)
├── thumbnails/          # Downloaded thumbnails
├── downloads/           # Downloaded videos + metadata
└── parsed/              # Channel parse results
```

---

## Changelog

### v3.8.0 (2026-04-12)
- **New Mode 2 — Download single video by URL**:
  - Paste any YouTube video URL to fetch instant statistics: title, channel, date, duration, views, likes, comments, resolution, categories, tags
  - After stats, choose from a sub-menu:
    - **Download video** — full quality/cookie selection (identical to batch download options); saves metadata `.txt` alongside the video
    - **Download thumbnail** — downloads max-resolution thumbnail to `thumbnails/`
  - Fetches info via yt-dlp (zero API quota consumed)
- **Menu renumbered**: old Mode 2 (Parse channel) is now Mode 3, old Mode 3 (Batch download) is now Mode 4, old Mode 4 (Thumbnails) is now Mode 5
- Version bump: `3.7.1` → `3.8.0`

### v3.7.1 (2026-04-11)
- **Cookie validation** — when using option 3 (cookies.txt), the tool now runs a quick lightweight test against YouTube before starting any real download; expired or invalid cookies are detected immediately with a clear error message
- **Smarter cookie file UX** — option 3 now shows two choices: press `[Enter]` to auto-scan the script folder (the most common workflow) or type a custom path to a file or folder
- **Auto-remove from videolinks.txt** — each URL is deleted from `videolinks.txt` immediately after a successful download; interrupted batch sessions resume from where they left off without re-downloading already completed videos

### v3.7 (2026-04-09)
- **YouTube JS challenge fix** — added `remote_components: ejs:github` and `js_runtimes: node` to yt-dlp options. YouTube encrypts stream URLs via an `n`-parameter JS challenge; without a solver only storyboard thumbnails were visible. EJS solver script is downloaded from GitHub on first run and cached locally
- **Cookie file auto-detect** — option 3 now accepts a folder path; automatically finds `cookies.txt`, `www.youtube.com_cookies.txt`, or `youtube_cookies.txt` inside it
- **Fixed Chrome pre-copy bug** — removed broken SQLite→cookiefile pipe (caused `UnicodeDecodeError`); browser option now always uses `cookiesfrombrowser` with browser closed
- **Smart warning display** — shows actionable warnings (cookie expiry, JS runtime issues) while suppressing yt-dlp noise
- **Robust format fallback** — all quality levels now end with `/worst` as absolute last resort
- **Safer download flow** — `extract_info(process=False)` for title fetch (no format errors); `ydl.download()` for actual pipeline
- Node.js changed from **recommended** to **required**

### v3.6 (2026-04-09)
- **Cookie / authentication support** for all download modes:
  - New prompt before every download: choose *no cookies*, *browser cookies*, or *cookies file*
  - Supported browsers: Chrome, Firefox, Edge, Brave, Opera, Chromium
  - **Auto-retry**: if a video is blocked by YouTube's bot check and cookies were not used initially, the tool automatically queues the failed URLs and retries them with browser cookies after the batch finishes
- **Refactored download internals**:
  - `_build_ydl_opts()` — centralises yt-dlp option assembly
  - `_download_one()` — single-URL helper shared by first pass and retry
  - `_is_bot_error()` — detects bot/auth signals in error messages
- Version bump: `3.5` → `3.6`

### v3.5 (2026-03-05)
- **Channel parsing fix**: switched from `search().list()` to `playlistItems().list()` API
  - `search().list()` had a hard cap of ~500 results and often returned far fewer (e.g. 13 instead of 2000+)
  - `playlistItems().list()` returns **all** videos on a channel without any limit
- **Quota optimization**: channel parsing now costs **1 unit/call** instead of 100 units/call (100× cheaper)
- **Uploads playlist**: automatically derives the uploads playlist ID from the channel ID (`UC…` → `UU…`) with a fallback via `channels().list(part="contentDetails")`

### v3.4 (2026-02-16)
- **Search**: fetches ALL results via `nextPageToken` pagination (no longer limited to 25)
- **Paginated display**: results shown in batches; `[Space]` = next page, `[Escape]` = back to menu
- **Total count**: shows total number of found results before display
- **Save all**: saving to `find.txt` now includes ALL fetched results (URLs only)
- **Re-display**: added option to re-view search results from the actions menu
- **Filters**: replaced "Max results" with "Results per page" (controls display batch size)

### v3.3
- Added Mode 4 — Download Thumbnails (single video / entire channel)
- Clean download progress bar with speed and ETA
- Post-processing status messages (merging, converting)
- API key quota check on startup

---

## License

This project is for personal use. Respect YouTube's Terms of Service when using this tool.
