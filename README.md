# WSJ TOEIC Reader

Automatically scrape Wall Street Journal articles, translate them to Chinese using AI, and generate bilingual PDF study materials for TOEIC preparation.

## Features

- **Automated Scraping** - Fetches articles from WSJ homepage using Playwright + Chrome Remote Debug
- **AI Translation** - Uses Google Gemini Flash models (default `gemini-2.5-flash`)
- **Per-Article Calls** - Translates articles one by one for better stability on paid API
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
# Optional: override model (default: gemini-2.5-flash)
# GEMINI_MODEL=gemini-2.5-flash
```

## Usage

### 1. Run the Scraper

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

# Skip TOEIC vocabulary extraction for faster translation
python run_scraper.py --no-vocab
wsj-scraper --no-vocab

# Customize vocabulary count (1-20)
python run_scraper.py --vocab-count 5
wsj-scraper --vocab-count 5
```

By default, `run_scraper.py`/`wsj-scraper` will auto-start debug Chrome on port 9222 when needed, and auto-close it when finished to avoid accumulating background Chrome tasks.

Press `Ctrl+C` to interrupt; the program exits gracefully and cleans up Chrome lifecycle automatically.

### 2. Find Your PDFs

Generated files are organized by date:

```
output/
└── YYYY-MM-DD/
    ├── pdf/   # Bilingual PDF study materials
    └── json/  # Raw translation data
```

When using the bundled binary (`dist/wsj-scraper-cli`), output defaults to the **current working directory** (where you run the command), not the temporary PyInstaller extraction folder.

Optional overrides:

```bash
WSJ_OUTPUT_DIR="$HOME/Documents/wsj-output" ./dist/wsj-scraper-cli --url "..."
WSJ_PROJECT_ROOT="$HOME/wsj-runtime" ./dist/wsj-scraper-cli --url "..."
```

### 3. Debug Chrome Scripts (Optional)

```bash
./start_chrome.sh
./stop_chrome.sh
```

These helper scripts are only for debugging or manual lifecycle control.

### 4. Process Custom Transcripts
You can also process long text files (like interview transcripts). Example for Naval Ravikant's full transcript:
```bash
python naval_study.py
```

### 5. Build Standalone CLI App

```bash
# Single-file binary (distribution friendly, slower startup)
./build_cli.sh --onefile

# Directory build (faster startup, larger folder)
./build_cli.sh --onedir
```

Outputs:

- onefile: `dist/wsj-scraper-cli`
- onedir: `dist/wsj-scraper-cli-fast/wsj-scraper-cli-fast`

## Speed Tips

- `--no-vocab`: fastest option; skips vocabulary extraction (usually saves noticeable time)
- `--no-json`: skips JSON file save and writes PDF only
- `--keep-chrome`: keep debug Chrome alive if you run multiple URLs back-to-back
- prefer `./build_cli.sh --onedir`: startup is faster than onefile on macOS

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
2. **Translation**: Sends each article to Gemini Flash model with JSON mode enabled (default `gemini-2.5-flash`)
3. **Vocabulary Extraction**: AI extracts 10 TOEIC-relevant words with phonetics, meanings, and example sentences
4. **PDF Generation**: Creates professional bilingual PDFs using ReportLab with proper Chinese font support

## API Usage

The default flow now translates per article (1 article = 1 API call), which avoids oversized responses and is more reliable for paid API users.

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

### Node Deprecation Warning (`DEP0169`)

This warning comes from Node-side Playwright internals and is non-fatal. The CLI now suppresses deprecation noise by default. To show all Node warnings again, set:

```bash
WSJ_SHOW_NODE_WARNINGS=1 python run_scraper.py
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Disclaimer

This tool is for personal educational use only. Please respect WSJ's Terms of Service and copyright. The developers are not responsible for any misuse of this tool.

## Contributing

Pull requests are welcome! Please open an issue first to discuss proposed changes.

---

Built with Playwright, Gemini AI, and ReportLab.
