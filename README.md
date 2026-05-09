# YouTube Channel Finder v4.6.0

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
    - **No cookies** — try without authentication first
    - **Browser cookies** — extract cookies from Firefox, Edge, Brave, Opera, or Chromium (Chrome 127+ may fail due to App-Bound Encryption)
    - **Cookies file** — supply a Netscape-format `cookies.txt` file:
      - Press `[Enter]` to auto-scan the script folder for `cookies.txt` automatically
      - Or type a custom path to a file or folder — the script auto-detects `cookies.txt`, `www.youtube.com_cookies.txt`, `youtube_cookies.txt`
      - **Cookie validation**: the tool tests cookies against YouTube before starting any download. If cookies are expired or invalid, an error is shown immediately
  - If downloading fails due to a bot-detection block, the tool automatically retries blocked videos with browser cookies
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
- Checks for `yt-dlp` updates on every launch and upgrades automatically

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

Export YouTube cookies using the **"Get cookies.txt LOCALLY"** Chrome extension and feed them to the script. This is the most reliable method because it works regardless of Chrome's App-Bound Encryption (127+).

#### Step 1 — Install the extension

1. Open **Google Chrome** (or Edge/Brave — any Chromium browser)
2. Go to the Chrome Web Store:  
   👉 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
3. Click **"Add to Chrome"** → confirm **"Add extension"**
4. *(Optional)* Pin the extension to the toolbar:
   - Click the **puzzle icon** 🧩 in the top-right of Chrome
   - Find **"Get cookies.txt LOCALLY"** and click the **pin** 📌 icon

#### Step 2 — Log into YouTube

1. Go to [youtube.com](https://www.youtube.com) in the same browser
2. Make sure you are **logged into your Google account**
3. Verify by checking that your **profile avatar** appears in the top-right corner (not a "Sign in" button)

#### Step 3 — Export cookies

1. Stay on **youtube.com** (any YouTube page works)
2. Click the **"Get cookies.txt LOCALLY"** extension icon in the toolbar (or via the puzzle menu)
3. The extension popup will open showing a list of cookies for the current site
4. Click **"Export"** (or **"Export as cookies.txt"** — exact label may vary)
5. A file named `www.youtube.com_cookies.txt` (or `cookies.txt`) will be **downloaded to your Downloads folder**

#### Step 4 — Place the cookies file

Move the exported `.txt` file to the **script folder** (where `youtube_finder.py` is located):

```
CHANNELFINDER/
├── youtube_finder.py
├── cookies.txt          ← place the exported file here
└── ...
```

> 💡 **Tip:** The script auto-detects any of these filenames:  
> `cookies.txt`, `www.youtube.com_cookies.txt`, `youtube_cookies.txt`  
> So you can keep the original filename — no renaming needed.

#### Step 5 — Use in the script

1. Run `youtube_finder.py`
2. When the **Cookies / Authentication** menu appears, pick **3** (Use cookies from a .txt file)
3. Press **Enter** to auto-scan the script folder — the file will be found automatically
4. The script **validates** the cookies against YouTube before starting any download
5. If validation passes (**OK ✓**) — downloads will proceed with full authentication

#### ⚠️ When cookies expire

Chrome rotates session tokens every few hours as a security measure. If you see this error:

```
Cookie validation failed — cookies are expired or invalid.
Re-export cookies from your browser and try again.
```

Simply **repeat Steps 3–4**: go to YouTube, click the extension, export fresh cookies, and replace the old file. This takes about 10 seconds.

> 💡 **Tip:** Don't close Chrome between exporting cookies and starting the download — the cookies are valid for the current active session. The faster you use them, the less chance they'll expire.

### Option C — Browser cookies (direct extraction)
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

## Version

Current version: **v4.6.0**

> Detailed change history is maintained in `GEMINI.md` and `CLAUDE.md` (AI session context files, not tracked in git).

---

## License

This project is licensed under the [MIT License](LICENSE).

> ⚠️ This tool interacts with YouTube. Please respect [YouTube's Terms of Service](https://www.youtube.com/t/terms) when using it.
