# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e .
playwright install chromium
cp .env.example .env  # then add GEMINI_API_KEY

# Run (auto-manages Chrome lifecycle)
python run_scraper.py                        # scrape 5 articles
python run_scraper.py --limit 10             # scrape 10 articles
python run_scraper.py --url "https://..."    # specific article
python run_scraper.py --no-vocab             # skip vocab extraction (faster)
python run_scraper.py --vocab-count 5        # 5 vocab words instead of 10

# Chrome lifecycle (if managing manually)
wsj-scraper --start-chrome
wsj-scraper --stop-chrome
```

No automated test suite exists — testing is manual by running against real URLs.

## Architecture

The pipeline has four sequential stages orchestrated by `run_scraper.py`:

1. **Scrape** (`wsj_scraper/scraper.py`) — Connects to a real Chrome instance via CDP (port 9222) using Playwright. Uses the existing browser's cookies/auth to bypass most paywalls. Applies playwright-stealth and random delays to avoid bot detection. Stores scraped articles in `.raw_cache/` until translation succeeds; tracks processed URLs in `.processed_articles.json`.

2. **Translate** (`wsj_scraper/translator.py`) — Sends all articles to Google Gemini 2.5 Flash in a **single batch API call** (chunked by `TRANSLATION_CHUNK_SIZE=3`). Returns bilingual paragraphs and optional TOEIC vocabulary with phonetics and example sentences. Handles 429 rate limits by reading the `retryDelay` field and waiting accordingly; uses exponential backoff for network errors.

3. **Generate PDF** (`wsj_scraper/pdf_generator.py`) — Creates bilingual side-by-side PDFs using ReportLab. Chinese text uses macOS system font (`/System/Library/Fonts/Supplemental/Songti.ttc`). Long paragraphs (>2000 chars) fall back to sequential layout instead of two-column.

4. **Output** — PDFs and JSON saved to `output/YYYY-MM-DD/pdf/` and `output/YYYY-MM-DD/json/`.

### Key files

| File | Purpose |
|------|---------|
| `run_scraper.py` | CLI entry point, Chrome lifecycle, pipeline orchestration |
| `wsj_scraper/config.py` | All configuration constants and env var overrides |
| `wsj_scraper/models.py` | `Article` and `TranslatedArticle` dataclasses |
| `wsj_scraper/scraper.py` | Playwright + CDP scraping |
| `wsj_scraper/translator.py` | Gemini batch translation |
| `wsj_scraper/pdf_generator.py` | ReportLab PDF generation |
| `upload_to_r2.sh` | 上传 PDF 到 Cloudflare R2 |

### Chrome process management

Chrome is launched with `--remote-debugging-port=9222` and positioned off-screen. The PID is stored at `~/.wsj_chrome_profile/chrome-debug-9222.pid`. By default, Chrome auto-starts before scraping and auto-stops after — use `--keep-chrome` to prevent auto-stop, or `--no-auto-start-chrome` to manage it yourself.

### Environment variables

- `GEMINI_API_KEY` — required for translation
- `WSJ_OUTPUT_DIR` — override output directory

## 上传到 R2

```bash
# 上传所有 PDF 到 R2
bash upload_to_r2.sh

# 只上传指定日期
bash upload_to_r2.sh --date 2026-03-14
```

- R2 bucket: `wsj-reader`
- Web viewer: `~/code/sites/wsj/`（独立 Pages 项目）
- 域名: `wsj.897654321.space`
