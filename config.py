import logging
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from rich.logging import RichHandler
from rich.console import Console

load_dotenv()

# Inisialisasi console Rich (bisa di-import ke file lain)
console = Console()

URL_FILE = os.getenv("URL_FILE", "urls.txt")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", 60000))
SCAN_TIMEOUT_SEC = int(os.getenv("SCAN_TIMEOUT_SEC", 180))

MAX_RETRIES = max(1, int(os.getenv("MAX_RETRIES", 3)))
RETRY_DELAY_SEC = max(0, int(os.getenv("RETRY_DELAY_SEC", 10)))

_download_limit = os.getenv("DOWNLOAD_LIMIT_RATE", "").strip()
DOWNLOAD_LIMIT_RATE = None if _download_limit.lower() in ("", "0", "off", "unlimited") else _download_limit
CONCURRENT_FRAGMENTS = max(1, int(os.getenv("CONCURRENT_FRAGMENTS", 8)))
MAX_CONCURRENT_DOWNLOADS = max(1, min(4, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", 1))))
PROGRESS_DELTA_SEC = max(1, int(os.getenv("PROGRESS_DELTA_SEC", 5)))
BROWSER_COOKIES = os.getenv("BROWSER_COOKIES", "").strip()
ENABLE_INTERACTIVE_FALLBACK = os.getenv("ENABLE_INTERACTIVE_FALLBACK", "true").strip().lower() in ("1", "true", "yes")
INTERACTIVE_TIMEOUT_SEC = max(10, int(os.getenv("INTERACTIVE_TIMEOUT_SEC", 60)))
PROXY = os.getenv("PROXY", "").strip()

# KONFIGURASI LOGGING RICH
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s", # Rich otomatis ngurus format waktu & level
    datefmt="[%X]",
    handlers=[
        RotatingFileHandler("app.log", maxBytes=1*1024*1024, backupCount=2, encoding='utf-8'),
        RichHandler(console=console, rich_tracebacks=True, markup=True) # Aktifkan UI Rich
    ]
)

logger = logging.getLogger("VideoDownloader")
