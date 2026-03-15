import logging
import sys
from pathlib import Path
from .config import LOG_DIR, LOG_LEVEL

def setup_logging(name: str) -> logging.Logger:
    """Setup and return a logger instance"""
    # Create logs directory if it doesn't exist
    LOG_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    if not logger.handlers:
        # File handler
        log_file = LOG_DIR / "scraper.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
    return logger

async def minimize_window(page):
    """Minimize the browser window using CDP"""
    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Browser.setWindowBounds", {
            "windowId": 1,
            "bounds": {"windowState": "minimized"}
        })
    except Exception:
        pass  # Fail silently is okay for cosmetic op
