# YouTube Channel Finder v4.9.2

![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

A console tool for researching and archiving YouTube content: search videos with filters, list every video of a channel or playlist, and download videos, audio and thumbnails in bulk.

Search and parsing use the official **YouTube Data API v3**; downloads use **yt-dlp** with built-in protection against YouTube's bot detection.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Avoiding "Sign in to confirm you're not a bot"](#avoiding-sign-in-to-confirm-youre-not-a-bot)
- [Getting a YouTube API key](#getting-a-youtube-api-key)
- [Files and folders](#files-and-folders)
- [Troubleshooting](#troubleshooting)

---

## Features

| Mode | What it does |
|------|--------------|
| **1 · Search videos** | Keyword search with filters (duration, quality, date, language); shows channel stats; save links, download videos or thumbnails |
| **2 · Single video** | Paste a URL → see views, likes, tags, resolution → download the video or its thumbnail |
| **3 · Parse channel** | Lists **every** video of a channel, split into long videos and Shorts; bulk download |
| **4 · Batch download** | Downloads all URLs from `videolinks.txt`; finished links are removed, so an interrupted batch resumes where it stopped |
| **5 · Thumbnails** | Max-resolution thumbnails for one video or a whole channel |
| **6 · Playlist parser** | Lists every video of a playlist; bulk download of videos or thumbnails |
| **7 · Sync channels** | Follows your favourite channels and downloads only the videos you don't have yet |
| **8 · Niche finder** | Finds the channels behind a topic, rates them and spots videos that far outperform their channel |

Also:

- **Quality choice**: 1080p, 720p, 480p, MP3 audio, or 4K/8K when the video has it
- **Export to CSV / Excel** from search, channel, playlist and niche results
- **Never downloads the same video twice** — every download is remembered
- **Ctrl+C stops safely** — the batch summary is shown and the rest can be resumed later
- **Metadata** saved next to each video (title, channel, views, likes, tags, description)
- **Several API keys** with automatic switching when one runs out of quota
- **Anti-bot protection**: PO tokens, human-like pauses, fresh login cookies on demand ([details](#avoiding-sign-in-to-confirm-youre-not-a-bot))
- **Self-updating**: dependencies and yt-dlp are updated on every launch

---

## Quick start

### 1. Install the requirements

| Program | Why | Download |
|---------|-----|----------|
| Python 3.8+ | runs the tool | [python.org](https://www.python.org/downloads/) |
| FFmpeg | merges video + audio, converts to MP4/MP3 | [ffmpeg.org](https://ffmpeg.org/download.html) |
| Node.js 22+ | solves YouTube's JavaScript challenge, runs the token server | [nodejs.org](https://nodejs.org/) |
| Git | fetches the token server once on first launch | [git-scm.com](https://git-scm.com/) |
| Chrome or Edge | *optional* — only for the [Cookie Extractor](#cookie-extractor) | — |

FFmpeg, Node.js and Git must be available in `PATH` (check with `ffmpeg -version`, `node -v`, `git --version`).

### 2. Get the code and Python packages

```bash
git clone https://github.com/kizer2m/CHANNELFINDER.git
cd CHANNELFINDER
pip install -r requirements.txt
```

### 3. Add an API key

Create `api_keys.txt` in the project folder and put your key(s) there, one per line ([how to get a key](#getting-a-youtube-api-key)). If the file is missing, the tool creates a template on first launch.

### 4. Run

| Windows | macOS / Linux |
|---------|---------------|
| double-click `run_search.cmd` | `python3 youtube_finder.py` |

On launch the tool updates its dependencies, starts the token server (the very first launch builds it, ~1 min), checks your API keys and opens the main menu.

---

## Usage

### 1 · Search videos

Enter a query, then set the filters (press Enter to skip any of them):

- **Duration**: under 4 min / 4–20 min / over 20 min
- **Quality**: SD / HD
- **Uploaded**: last hour / today / week / month / year
- **Language**: e.g. `en`, `ru`, `ja`
- **Results per page**: 1–50 (default 25)

All matching results are loaded, then shown page by page: **Space** for the next page, **Esc** to stop. Each result shows the channel's subscribers, total views and video count.

After the search you can save all links to `find.txt`, download the videos or thumbnails, open channel analytics, or **export everything to CSV** (views, likes, comments, duration, views per day, channel subscribers).

> Each search page costs 100 API quota units, so a large search can use a noticeable share of the daily 10,000.

### 2 · Single video by URL

Shows the video's statistics (no API quota used), then offers to download the video or its thumbnail.

### 3 · Parse channel

Accepts a channel URL, an `@handle` (any language, e.g. `@ОльгаКиселёва`) or just the channel name.

- Lists **all** videos, even on channels with thousands of uploads, at about 1 quota unit per 50 videos
- Saves the links to `parsed/<Channel>_long.txt` and `parsed/<Channel>_shorts.txt`
- Long videos and Shorts are separated by YouTube itself (Shorts can be up to 3 minutes, so length alone can't tell them apart); past live streams count as long videos
- Then lets you download long videos, Shorts or both, optionally together with thumbnails

Links are copied into `videolinks.txt` before downloading. If the download is interrupted, finish it later with **mode 4**.

Choose **Add channel to sync list** to keep getting the channel's new videos via **mode 7**, or **Export to CSV** for a spreadsheet of all its videos (with a Long/Short column).

### 4 · Batch download

Put video URLs into `videolinks.txt`, one per line (lines starting with `#` are ignored), and choose mode 4. Each downloaded link is removed from the file right away.

### 5 · Thumbnails

Downloads the highest-resolution thumbnail (falls back to HQ when no max-res version exists) for a single video or for every video of a channel. Files are named `Title [videoId].jpg`.

### 6 · Playlist parser

Accepts a playlist URL (`...?list=PL...`) or a bare playlist ID. Skips deleted and private videos, saves the list to `parsed/<Playlist>_playlist.txt`, and offers to download the videos or thumbnails or to export them to CSV.

### 7 · Sync channels

Keep a list of channels and download only what is new since the last check.

1. Add a channel here or from **mode 3** (*Add channel to sync list*). Choose what to follow — long videos, Shorts or both — and where to start: only videos published from now on, the last 30 days, or the whole channel.
2. Whenever you like, choose **Check & download new videos**. New videos of all channels are found, queued in `videolinks.txt` and downloaded.

A check costs about 1 API quota unit per channel. The list is stored in `channels.json`.

### 8 · Niche finder

Answers *"who makes videos on this topic, and what works?"*

1. Enter a topic, e.g. `sourdough bread`.
2. Choose how many videos to analyse (50–500), the upload period, language and an optional subscriber range — e.g. `1k-100k` to look only at small channels.
3. You get a table of the channels behind those videos:

| Column | Meaning |
|--------|---------|
| Subs | subscribers |
| Avg views | the channel's total views ÷ number of videos |
| V/Sub | avg views ÷ subscribers — above 1 means videos reach far beyond the subscriber base |
| 30d | videos uploaded in the last 30 days (is the channel active?) |
| Age | how long the channel has existed |
| Found | how many of the found videos belong to it |

Then you can:

- **Sort** by avg views, views per subscriber (*small but strong* channels), subscribers, activity or matches
- **Outlier videos** — videos with at least **3×** their channel's average views. If a small channel's video took off, the topic itself is in demand
- **Export to CSV** — two files: channels and videos (with the outlier score)
- **Add a channel to the sync list** or **parse it** (full video list, mode 3) by its number

The menu shows the quota cost before starting: about 2–3 units per analysed video (150 videos ≈ 300–450 of the daily 10,000).

### Exporting to CSV

Exports are saved to `exports/` as `<name>_<date>.csv`. They use `;` as the separator and UTF-8 with BOM, so a double-click opens them correctly in Excel (including non-English locales and non-Latin titles); Google Sheets and LibreOffice read them as well.

### Download options

Every download asks two questions.

**Quality**

| Option | Result |
|--------|--------|
| 1080p / 720p / 480p | MP4 (best available up to that height) |
| Audio only | MP3, 192 kbps |
| Ultra High | checks the video for 4K/8K and lets you pick the exact resolution |

**Cookies**

| Option | When to use |
|--------|-------------|
| 1 · No cookies | default; works for most public videos |
| 2 · Fresh cookies from tool browser profile | when YouTube starts blocking; uses your signed-in session ([Cookie Extractor](#cookie-extractor)) |
| 3 · Cookies from a .txt file | if you already have a `cookies.txt` exported some other way |

Videos are saved to `downloads/` as `Title [videoId].mp4` together with a `.txt` file of metadata.

**Already downloaded?** Every finished video is recorded in `downloads/downloaded_videos.txt` (MP3s in `downloaded_audio.txt`); files already in `downloads/` count too. If a list contains videos you already have, you are asked whether to skip them — no request is sent to YouTube for skipped videos. Having the MP4 doesn't block downloading the MP3 and vice versa.

**Stopping:** press **Ctrl+C** at any time. The current batch stops, you see how many videos were finished, and the rest stays in `videolinks.txt` for **mode 4**. A half-downloaded file continues where it stopped. Ctrl+C in the main menu exits the program.

---

## Avoiding "Sign in to confirm you're not a bot"

YouTube limits how many videos one IP address can request: roughly **300 videos per hour** without an account and about **2,000 per hour** with a signed-in account. Past that, it answers *"Sign in to confirm you're not a bot"*.

### What the tool does automatically

- **PO tokens.** A small local server ([bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)) generates the same proof-of-origin tokens a real browser player sends. It is built on the first launch, started in the background on every launch and stopped on exit.
- **One request per video.** Each video's info is fetched once and reused for the download and the metadata file.
- **Human-like pacing.** A random 6–14 s pause between videos, plus a 1.5–3 min break after every 25 videos.
- **Stops on the first block.** Further requests would only make the block longer. Unfinished links stay in `videolinks.txt`.
- **Retries with your login.** If a batch without cookies gets blocked, the rest of it is retried with fresh cookies from the tool's browser profile.
- **Up-to-date yt-dlp.** yt-dlp is updated to the latest *nightly* build on every launch; fixes for YouTube changes appear there first.

### If you are blocked anyway

1. **Wait 30–60 minutes.** Blocks without an account are temporary. Then continue with **mode 4**.
2. **Use a signed-in session.** Choose cookie option **2**. A secondary Google account is recommended, so your main account is never at risk.

> VPNs and Cloudflare WARP don't help: shared IP addresses are treated with *more* suspicion by Google, not less.

### Cookie Extractor

`extract_cookies.cmd` (or `python3 cookie_extractor.py`) saves your YouTube login to `cookies.txt`.

Chrome 127+ and Edge encrypt their cookies so that no other program can read them, which is why "import cookies from browser" usually fails. The extractor works around this:

1. It uses its **own browser profile** in `browser_profile/`. Your normal browser is never touched and can stay open.
2. **First run:** a regular Chrome/Edge window opens. Sign in to YouTube, then **close the window**.
3. **Every later run:** the profile is opened invisibly, youtube.com is loaded, the cookies are written to `cookies.txt` and the browser closes (about 10 seconds).

Since nothing else ever opens this profile, YouTube doesn't invalidate the saved session, unlike cookies exported from a browser you use every day, which stop working within hours.

```bash
extract_cookies.cmd                    # menu: refresh / sign in / import from Firefox
python3 cookie_extractor.py --refresh  # refresh without questions (exit code 0 = success)
```

You rarely need to run it by hand: cookie option **2** in any download does the same automatically.

> ⚠️ `cookies.txt` and `browser_profile/` contain your logged-in session. They are excluded from git — never share or upload them.

---

## Getting a YouTube API key

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Go to **APIs & Services → Library**, find **YouTube Data API v3** and click **Enable**.
3. Go to **APIs & Services → Credentials → Create credentials → API key**.
4. **Restrict the key:** open it, set *API restrictions* to **YouTube Data API v3** and save. A restricted key is useless for anything else if it ever leaks.
5. Paste the key into `api_keys.txt`.

Each key has **10,000 quota units per day**:

| Action | Cost |
|--------|------|
| Search (one page of up to 50 results) | 100 units |
| Channel / playlist listing | 1 unit per 50 videos |
| Channel stats | 1 unit |
| Downloads, video info, thumbnails | free (no API used) |

Add several keys (one per line) to raise the daily limit. At startup every key is tested, and the tool switches to the next one automatically when a key runs out.

> 🔒 Never commit `api_keys.txt` — it is already in `.gitignore`. If a key was ever published, delete it in the Cloud Console and create a new one.

---

## Files and folders

```
CHANNELFINDER/
├── youtube_finder.py      main program
├── cookie_extractor.py    Cookie Extractor
├── run_search.cmd         Windows launcher
├── extract_cookies.cmd    Cookie Extractor launcher (Windows)
├── requirements.txt       Python packages
│
├── api_keys.txt           🔒 your API keys
├── cookies.txt            🔒 exported YouTube cookies
├── browser_profile/       🔒 Cookie Extractor's browser profile
├── pot-provider/          token server (built automatically)
│
├── videolinks.txt         links waiting for download (mode 4)
├── channels.json          channels followed by mode 7
├── exports/               CSV exports
├── find.txt               links saved from searches
├── parsed/                channel and playlist link lists
├── downloads/             videos + metadata + list of downloaded videos
└── thumbnails/            thumbnails
```

Everything below `requirements.txt` is created by the tool and excluded from git. 🔒 marks private files.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| *Sign in to confirm you're not a bot* | Wait 30–60 min, or use cookie option 2 — see [above](#avoiding-sign-in-to-confirm-youre-not-a-bot) |
| *PO Token server build failed* | Install Git and Node.js 22+, make sure they are in `PATH`, restart the tool |
| *PO Token server vX running, plugin is vY* | An old server is still running: end the `node.exe` process (Task Manager) and restart the tool |
| Only very low quality or no formats | Check `node -v` (22+ needed); the first download also needs internet access to fetch the challenge solver |
| *Cookie validation failed* | Run `extract_cookies.cmd` → **2** and sign in again |
| *Quota exhausted* on all keys | Quota resets daily (midnight Pacific time); add more keys to `api_keys.txt` |
| Video downloaded without sound / not MP4 | FFmpeg is missing — install it and add it to `PATH` |

---

## Version

Current version: **v4.9.2**

---

## License

[MIT](LICENSE)

> This tool interacts with YouTube. Please respect the [YouTube Terms of Service](https://www.youtube.com/t/terms) and the rights of content creators — download only what you are allowed to.
