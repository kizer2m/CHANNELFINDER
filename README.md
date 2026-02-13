# YouTube Channel Finder v3.3

A powerful command-line tool for searching YouTube videos, parsing channels, downloading videos, and grabbing thumbnails — all powered by the YouTube Data API v3 with automatic API key rotation.

---

## Features

### 🔍 Mode 1 — Search Videos
- Search YouTube by keywords with advanced filters:
  - **Duration**: any / short (<4 min) / medium (4–20 min) / long (>20 min)
  - **Quality**: any / SD / HD
  - **Date range**: last hour / today / week / month / year
  - **Language**: filter by relevance language code (e.g. `ru`, `en`, `ja`)
  - **Max results**: 1–50
- Displays results with channel analytics (subscribers, total views, video count)
- **Post-search actions**:
  - Save video links to `find.txt` (links only, no titles)
  - Download max-resolution thumbnails
  - Download selected videos as MP4 with quality selection
  - View detailed channel analytics

### 📋 Mode 2 — Parse Channel
- Accepts channel URL, `@handle`, or free-text search
- Fetches **all** videos from a channel (paginated)
- Classifies videos into **Long** (>60s) and **Shorts** (≤60s)
- Saves results to `parsed/` folder as separate files with links only:
  - `ChannelName_long.txt`
  - `ChannelName_shorts.txt`

### ⬇️ Mode 3 — Batch Download
- Reads video URLs from `videolinks.txt` (one URL per line)
- Quality selection: Best / 720p / 480p / Audio-only (MP3)
- Re-encodes to MP4 automatically via FFmpeg
- **Clean download UI**:
  - Green progress bar with speed and ETA
  - No warnings cluttering the console
  - Only critical errors are shown
- Saves full video metadata to a `.txt` file per video (title, channel, views, likes, tags, description, etc.)
- Handles duplicate titles by appending `[videoId]` to filenames

### 🖼️ Mode 4 — Download Thumbnails
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
- **Node.js** (recommended) — for full yt-dlp format support
  - Download from [nodejs.org](https://nodejs.org/)

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

> **Tip:** Each API key has a daily quota of **10,000 units**. A single search costs ~100 units. Add multiple keys to extend your daily capacity — the script rotates through them automatically.

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

## License

This project is for personal use. Respect YouTube's Terms of Service when using this tool.
