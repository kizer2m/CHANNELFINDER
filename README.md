# YouTube Channel Finder v4.7.0

A powerful **cross-platform** command-line tool for searching YouTube videos, parsing channels, downloading videos, and grabbing thumbnails — all powered by the YouTube Data API v3 with automatic API key rotation. Runs on **Windows, macOS, and Linux** with no platform-specific dependencies.

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
- Accepts channel URL, `@handle` (including non-Latin handles like `@ОльгаКиселёва`), or free-text search
- **Handles percent-encoded URLs**: `@%D0%9E%D0%BB%D1%8C%D0%B3%D0%B0...` is decoded automatically
- Fetches **all** videos from a channel using the **uploads playlist** (`playlistItems` API)
  - No result cap — works correctly even for channels with **thousands** of videos
  - Uses only **1 quota unit** per API call (100× cheaper than search)
- Classifies videos into **Long** (>60s) and **Shorts** (≤60s)
- Saves results to `parsed/` folder as separate files with links only:
  - `ChannelName_long.txt`
  - `ChannelName_shorts.txt`
- **After parsing, a multi-level download menu appears:**
  1. **Download long videos** — opens sub-menu:
     - Download video only (quality/cookies/proxy selection, identical to Mode 4)
     - Download video + thumbnails (thumbnails saved to `thumbnails/ChannelName_long/`)
     - Back
  2. **Download shorts** — same sub-menu for shorts
  3. **Download long + shorts** — same sub-menu for all videos combined
  4. **Back to main menu**
- URLs are **copied to `videolinks.txt`** before download (originals in `_long.txt`/`_shorts.txt` are **never deleted**); already-present URLs are skipped to avoid duplicates
- Each successfully downloaded URL is **removed from `videolinks.txt`** so interrupted sessions resume cleanly
- Thumbnails downloaded in **max-resolution** (fallback to HQ), one subfolder per video type
- Full metadata `.txt` file saved per downloaded video (same as Mode 4)

### ⬇️ Mode 4 — Batch Download
- Reads video URLs from `videolinks.txt` (one URL per line)
- **Quality selection** (5 tiers):
  - `1` — **1080p** (MP4)
  - `2` — **720p** (MP4)
  - `3` — **480p** (MP4)
  - `4` — **Audio only** (MP3, 192 kbps)
  - `5` — **Ultra High (4K/8K)** — probes the video for available resolutions ≥ 2160p; lets you pick exact height (2160p 4K, 4320p 8K, etc.); shows a "not available" message with skip/exit options if the video has no UHD stream
- Re-encodes to MP4 automatically via FFmpeg
- **🍪 Cookie / Authentication support**:
  - Choose how to handle YouTube authentication before every download:
    - **No cookies** — PO tokens + browser-like player clients (works for most public videos)
    - **Fresh cookies from tool browser profile** — exports a signed-in session to `cookies.txt` automatically (see [Cookie Extractor](#-cookie-extractor-extract_cookiescmd))
    - **Cookies file** — supply a Netscape-format `cookies.txt` file:
      - Press `[Enter]` to auto-scan the script folder for `cookies.txt` automatically
      - Or type a custom path to a file or folder — the script auto-detects `cookies.txt`, `www.youtube.com_cookies.txt`, `youtube_cookies.txt`
      - **Cookie validation**: the tool tests cookies against YouTube before starting any download. If cookies are expired or invalid, an error is shown immediately
  - If a bot-detection block hits a no-cookie batch, the rest of the batch is retried with fresh cookies from the tool profile
- **🛡️ Anti-bot pacing**: one extraction per video, random 6–14 s pauses between videos and a 1.5–3 min break every 25 videos; the batch stops at the first block instead of hammering YouTube
- **Auto-remove completed URLs**: each URL is removed from `videolinks.txt` immediately after a successful download, so interrupted sessions resume cleanly from where they left off
- **JavaScript challenge solver** — uses Node.js + EJS remote component to decrypt YouTube stream URLs (required since 2025; without it only storyboard thumbnails are available)
- **CStyle Console download UI**:
  - Separate progress lines for each stream: `► Video`, `♫ Audio`
  - Post-processing phases with animated progress: `⊕ Merging`, `⊛ Converting`, `♪ Extracting`
  - Real-time speed (MB/s) and ETA display
  - Spinner animation, phase-aware icons, and `✓` checkmark on completion
- Saves full video metadata to a `.txt` file per video (title, channel, views, likes, tags, description, etc.)
- Handles duplicate titles by appending `[videoId]` to filenames

### 🖼️ Mode 5 — Download Thumbnails
- **Single video**: paste a video URL → downloads max-resolution thumbnail
- **Entire channel**: paste a channel URL or `@handle` → downloads all video thumbnails
- Thumbnails saved as `Title [videoId].jpg` (max-res with fallback to HQ)
- All saved to `thumbnails/` folder

### ▶️ Mode 6 — Playlist Parser
- Paste any YouTube playlist URL (`?list=PL...`) or raw playlist ID
- Fetches **all accessible videos** in the playlist via `playlistItems` API (1 quota unit/page)
- Skips deleted and private videos automatically
- Displays a **preview** of the first 5 videos with position numbers and full count
- Saves the full URL list to `parsed/<PlaylistName>_playlist.txt` with header metadata
- **Post-parse action menu:**
  1. **Download videos** — full quality/cookie selection (same as Mode 4: 1080p/720p/480p/MP3/Ultra HD)
  2. **Download thumbnails** — saves all thumbnails to `thumbnails/<PlaylistName>/` (max-res with HQ fallback, named `Title [videoId].jpg`)
  3. **Back to main menu**

### 🔑 API Key Management
- Keys stored in `api_keys.txt` (one per line)
- On startup, each key is tested and status displayed:
  - ✓ Active
  - ✗ Quota exhausted
  - ✗ Invalid key
- Auto-rotation: if a key's quota runs out mid-operation, the script switches to the next available key seamlessly
- First valid key is selected automatically as the starting key

### 🔄 Auto-Update
- On every launch updates all dependencies and shows the installed version (or the pip error if an update fails)
- `yt-dlp` follows the **nightly** channel (recommended by yt-dlp for YouTube — fixes arrive there first), with `[default]` extras

### 🎫 PO Token Provider
- Uses [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) to generate YouTube *Proof-of-Origin* tokens, the same BotGuard attestation a real browser player sends
- On first launch the token server is cloned and built into `pot-provider/` (needs Git + Node.js 22+, ~1 min); it is rebuilt automatically when the plugin version changes
- Started in the background on launch and stopped on exit; while it runs, yt-dlp uses the token-backed `mweb` + `web_safari` clients

### 🗂️ Startup Environment Check
- Runs automatically after the update check on every launch
- Verifies all required items exist; **creates anything missing** and reports it:
  - `thumbnails/`, `downloads/`, `parsed/` — folders created if absent
  - `videolinks.txt` — created with a comment template if absent
  - `find.txt` — created empty if absent
  - `api_keys.txt` — if missing, creates a commented template **and shows a warning** to add real keys
- **Silent on clean installs**: if everything already exists, no output is shown
- Each created item shown as `Created` (yellow); already-present items shown as `OK` (green) only when the block appears

---

## Installation

### Prerequisites

- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — required for video merging and MP4 conversion
  - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
  - Add to system PATH
- **Node.js 22+** — **required** for YouTube JS challenge solving and the PO Token server
  - Download from [nodejs.org](https://nodejs.org/)
  - Add to system PATH
- **Git** — used once to fetch the PO Token server ([git-scm.com](https://git-scm.com/))
- **Google Chrome or Microsoft Edge** — used by the Cookie Extractor (optional)

### Setup

1. **Clone or download** the project folder

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   This installs:
   - `google-api-python-client` — YouTube Data API
   - `yt-dlp[default]` — video downloading
   - `bgutil-ytdlp-pot-provider` — PO Token plugin for yt-dlp
   - `websocket-client` — used by the Cookie Extractor

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

YouTube limits anonymous sessions to roughly **300 videos / hour**. The tool stays under that by itself (PO tokens, one request per video, random pauses). If a block still happens:

1. **Wait 30–60 minutes** — guest blocks are temporary. Unfinished URLs stay in `videolinks.txt`; resume with Mode 4.
2. **Use a signed-in session** — accounts get a much higher limit (~2000 videos / hour). Pick **2 (Fresh cookies from tool browser profile)** in the cookie menu. A secondary Google account is recommended.

> ℹ️ VPNs / Cloudflare WARP don't help: shared IPs are flagged by Google *more*, not less.

### 🍪 Cookie Extractor (`extract_cookies.cmd`)

Chrome 127+ and Edge encrypt cookies with *App-Bound Encryption* — nothing outside the browser (including yt-dlp's `--cookies-from-browser`) can read them. The extractor solves this by letting the browser itself hand the cookies over:

- It keeps a **separate browser profile** in `browser_profile/` — your main Chrome is never touched and may stay open
- **First run:** a normal Chrome/Edge window opens — sign in to YouTube, then **close the window**
- **After that:** the profile is opened invisibly, youtube.com is loaded (refreshing the session), the cookies are written to `cookies.txt` and the browser closes (~10 s)
- Because only the tool opens this profile, YouTube does not rotate the exported session — no more "cookies expired after a few hours"

Run it standalone:
```bash
extract_cookies.cmd              # menu: refresh / sign in / import from Firefox
python cookie_extractor.py --refresh   # non-interactive refresh (exit code 0 = ok)
```
or pick **2** in the cookie menu of any download — the same refresh runs automatically.

> 🔒 `cookies.txt` and `browser_profile/` contain your login session — they are gitignored; never share them.

### Manual alternative — cookies.txt from an extension

Export cookies with the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension while on youtube.com, put the file in the script folder and pick **3** in the cookie menu. Cookies exported from your everyday browser expire within hours because the browser keeps rotating the session.

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
├── cookie_extractor.py  # Cookie Extractor (fresh cookies.txt from a dedicated browser profile)
├── extract_cookies.cmd  # Cookie Extractor launcher
├── cookies.txt          # Exported cookies (gitignored)
├── browser_profile/     # Dedicated browser profile for cookies (gitignored)
├── pot-provider/        # PO Token server, built on first launch (gitignored)
├── videolinks.txt       # URLs for batch download (Mode 3)
├── find.txt             # Saved search results (links)
├── thumbnails/          # Downloaded thumbnails
├── downloads/           # Downloaded videos + metadata
└── parsed/              # Channel parse results
```

---

## Version

Current version: **v4.7.0**

> Detailed change history is maintained in `GEMINI.md` and `CLAUDE.md` (AI session context files, not tracked in git).

---

## License

This project is licensed under the [MIT License](LICENSE).

> ⚠️ This tool interacts with YouTube. Please respect [YouTube's Terms of Service](https://www.youtube.com/t/terms) when using it.
