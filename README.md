# WSJ TOEIC Reader

Automatically scrape Wall Street Journal articles, translate them to Chinese using AI, and generate bilingual PDF study materials for TOEIC preparation.

## Features

- **Automated Scraping** - Fetches articles from WSJ homepage using Playwright + Chrome Remote Debug
- **AI Translation** - Uses Google Gemini 2.5 Flash for high-quality English-Chinese translation
- **Batch Processing** - Translates multiple articles in a single API call (saves 90% API quota)
- **TOEIC Vocabulary** - Extracts 10 TOEIC-relevant vocabulary words per article with phonetics, definitions, and example sentences
- **Bilingual PDF** - Generates professional side-by-side English-Chinese PDF documents
- **Smart Retry** - Handles network instability with exponential backoff (up to 10 retries)
- **Rate Limit Handling** - Automatically waits and retries on API rate limits (429)

## Sample Output

```
output/
└── 2026-02-01/
    ├── pdf/
    │   ├── How_America_First_Risks_Becoming_America_Alone.pdf
    │   ├── The_Vibe_in_the_Crypto_Market_Right_Now_Stay_Ali.pdf
    │   └── ...
    └── json/
        ├── How_America_First_Risks_Becoming_America_Alone.json
        └── ...
```

## Requirements

- macOS (tested on macOS 15+)
- Python 3.11+
- Google Chrome
- [Gemini API Key](https://aistudio.google.com/apikey) (free tier available)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/wsj-toeic-reader.git
cd wsj-toeic-reader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install CLI command (wsj-scraper)
pip install -e .

# Install Playwright browsers
playwright install chromium

# Configure API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## Usage

### 1. Start Chrome in Debug Mode

```bash
# Start from CLI app
wsj-scraper --start-chrome

# Or use shell helper
./start_chrome.sh
```

This starts Chrome with remote debugging enabled (port 9222). The window is hidden off-screen to avoid interrupting your work.

### 2. Run the Scraper

```bash
source venv/bin/activate

# Scrape homepage and translate 5 articles (default)
python run_scraper.py

# Same behavior via installed CLI command
wsj-scraper

# Scrape 10 articles
python run_scraper.py --limit 10
wsj-scraper --limit 10

# Scrape a specific article URL
python run_scraper.py --url "https://www.wsj.com/articles/example-article"
wsj-scraper --url "https://www.wsj.com/articles/example-article"

# Keep Chrome alive after scraping (default is auto-close 9222 Chrome)
python run_scraper.py --keep-chrome
wsj-scraper --keep-chrome

# Show browser window for debugging
python run_scraper.py --no-headless
wsj-scraper --no-headless

# Skip JSON output, generate PDF only
python run_scraper.py --no-json
wsj-scraper --no-json

# If you want to manage Chrome lifecycle yourself
wsj-scraper --no-auto-start-chrome --keep-chrome
```

By default, `run_scraper.py`/`wsj-scraper` will auto-start debug Chrome on port 9222 when needed, and auto-close it when finished to avoid accumulating background Chrome tasks.

### 3. Find Your PDFs

Generated files are organized by date:

```
output/
└── YYYY-MM-DD/
    ├── pdf/   # Bilingual PDF study materials
    └── json/  # Raw translation data
```

### 4. Manually Stop Debug Chrome (Optional)

```bash
wsj-scraper --stop-chrome

# Or use shell helper
./stop_chrome.sh
```

Use this if you started Chrome with `--keep-chrome` and want to stop it later.

### 5. Process Custom Transcripts
You can also process long text files (like interview transcripts). Example for Naval Ravikant's full transcript:
```bash
python naval_study.py
```

### 6. Build Standalone CLI App

```bash
./build_cli.sh
```

This generates a standalone binary at `dist/wsj-scraper-cli`.

## Project Structure

```
wsj-toeic-reader/
├── run_scraper.py          # Main entry point
├── pyproject.toml          # CLI packaging config
├── build_cli.sh            # Build standalone CLI binary
├── start_chrome.sh         # Chrome launcher script
├── stop_chrome.sh          # Chrome stopper script
├── wsj_scraper/
│   ├── config.py           # Configuration settings
│   ├── scraper.py          # Web scraping logic
│   ├── translator.py       # AI translation (Gemini API)
│   └── pdf_generator.py    # PDF generation
├── output/                 # Generated files
└── .env                    # API keys (not in git)
```

## How It Works

1. **Scraping**: Connects to Chrome via CDP (Chrome DevTools Protocol) and extracts article content from WSJ
2. **Translation**: Sends all articles to Gemini 2.5 Flash in a single batch request with JSON mode enabled
3. **Vocabulary Extraction**: AI extracts 10 TOEIC-relevant words with phonetics, meanings, and example sentences
4. **PDF Generation**: Creates professional bilingual PDFs using ReportLab with proper Chinese font support

## API Usage

The batch translation feature significantly reduces API calls:

| Articles | Traditional | This Project |
|----------|-------------|--------------|
| 5        | 5 calls     | 1 call       |
| 10       | 10 calls    | 1 call       |

Gemini 2.5 Flash free tier: 15 requests/minute, 1500 requests/day

## Troubleshooting

### Chrome Connection Failed

```
请先用以下命令启动 Chrome：
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

Solution: Run `./start_chrome.sh` before running the scraper.

### Rate Limit (429)

The scraper automatically waits and retries. If you see repeated 429 errors, wait a few minutes before trying again.

### Network Errors

Network instability is handled with exponential backoff (15s, 30s, 45s, 60s...). The scraper will retry up to 10 times.

### JSON Decode Errors

If translation output is truncated, the scraper will attempt to parse partial results. Reduce `--limit` if this happens frequently.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Disclaimer

This tool is for personal educational use only. Please respect WSJ's Terms of Service and copyright. The developers are not responsible for any misuse of this tool.

## Contributing

Pull requests are welcome! Please open an issue first to discuss proposed changes.

---

Built with Playwright, Gemini AI, and ReportLab.
