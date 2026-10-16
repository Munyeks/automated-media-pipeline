import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from plyer import notification
from playwright.sync_api import sync_playwright
from rich.prompt import Prompt

from config import (
    logger,
    console,
    URL_FILE,
    MAX_RETRIES,
    RETRY_DELAY_SEC,
    MAX_CONCURRENT_DOWNLOADS,
    ENABLE_INTERACTIVE_FALLBACK,
    INTERACTIVE_TIMEOUT_SEC,
    PROXY,
)
from media_handler import MediaHandler
from network_interceptor import NetworkInterceptor

active_browsers = set()


def get_headless_choice() -> bool:
    console.print("\n[bold cyan]=== PENGATURAN TAMPILAN BROWSER ===[/bold cyan]")
    console.print("[bold]1.[/bold] Mode Headless (browser di latar belakang)")
    console.print("[bold]2.[/bold] Mode Visual (browser tampil di layar)")
    return Prompt.ask("\n[bold yellow]Pilih angka[/bold yellow]", choices=["1", "2"], default="2") == "1"


def read_queue() -> list[str]:
    with open(URL_FILE, "r", encoding="utf-8-sig") as file:
        return list(dict.fromkeys(line.strip() for line in file if line.strip()))


def save_queue(urls: list[str]) -> None:
    """Replace the queue atomically so an interruption cannot truncate it."""
    queue_path = os.path.abspath(URL_FILE)
    queue_dir = os.path.dirname(queue_path) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".urls-", suffix=".tmp", dir=queue_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            for url in urls:
                file.write(url + "\n")
        os.replace(temp_path, queue_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def notify_complete(title: str) -> None:
    try:
        short_title = title[:40] + "..." if len(title) > 40 else title
        notification.notify(
            title="Unduhan selesai",
            message=f"{short_title} berhasil disimpan!",
            app_name="Private Downloader",
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Notifikasi desktop tidak tersedia: %s", exc)


def process_url(target_url: str, media: MediaHandler, format_yt: str, is_headless: bool) -> tuple[bool, str]:
    """Download one URL. Safe to run in a worker thread."""
    interceptor = NetworkInterceptor()
    clean_title = "Video_Unduhan_Otomatis"

    # Let yt-dlp's maintained site extractors handle the page first.
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("[%s] yt-dlp langsung (%s/%s).", target_url, attempt, MAX_RETRIES)
        if media.download_video(target_url, "AUTO", format_yt):
            return True, clean_title
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SEC)

    # A separate Playwright runtime per fallback keeps its sync API inside the
    # worker thread and prevents browser cookies from crossing between URLs.
    logger.info("[%s] Mencoba mengenali media yang dimuat halaman.", target_url)
    browser_args = {"headless": is_headless}
    if PROXY:
        browser_args["proxy"] = {"server": PROXY}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**browser_args)
            active_browsers.add(browser)
            try:
                browser_context = browser.new_context(viewport={"width": 1280, "height": 720})
                try:
                    extracted_url, clean_title, video_headers = interceptor.extract_link(
                        browser_context,
                        target_url,
                        is_interactive=not is_headless,
                        interactive_timeout_sec=INTERACTIVE_TIMEOUT_SEC,
                    )
                finally:
                    browser_context.close()
            finally:
                active_browsers.discard(browser)
                browser.close()
    except Exception as exc:
        logger.warning("[%s] Fallback browser gagal: %s", target_url, exc)
        return False, clean_title

    # Jika mode headless gagal mendeteksi video, buka browser visual untuk interaksi pengguna
    if not extracted_url and is_headless and ENABLE_INTERACTIVE_FALLBACK:
        console.print(
            f"\n[bold yellow]⚠️ [{target_url}] Media belum terdeteksi di latar belakang.[/bold yellow]\n"
            f"[bold cyan]Membuka browser visual selama {INTERACTIVE_TIMEOUT_SEC} detik... Silakan selesaikan Captcha atau klik tombol Play di video jika diperlukan![/bold cyan]"
        )
        visual_args = {"headless": False}
        if PROXY:
            visual_args["proxy"] = {"server": PROXY}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**visual_args)
                active_browsers.add(browser)
                try:
                    browser_context = browser.new_context(viewport={"width": 1280, "height": 720})
                    try:
                        extracted_url, clean_title, video_headers = interceptor.extract_link(
                            browser_context,
                            target_url,
                            is_interactive=True,
                            interactive_timeout_sec=INTERACTIVE_TIMEOUT_SEC,
                        )
                    finally:
                        browser_context.close()
                finally:
                    active_browsers.discard(browser)
                    browser.close()
        except Exception as exc:
            logger.warning("[%s] Fallback browser interaktif gagal: %s", target_url, exc)

    if not extracted_url:
        logger.warning("[%s] Tidak ditemukan playlist atau file media yang didukung.", target_url)
        return False, clean_title

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("[%s] Unduh media terdeteksi (%s/%s).", target_url, attempt, MAX_RETRIES)
        if media.download_video(extracted_url, clean_title, format_yt, headers=video_headers):
            return True, clean_title
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SEC)

    return False, clean_title


def main():
    if not os.path.exists(URL_FILE):
        logger.error("File %s tidak ditemukan. Buat file tersebut dan masukkan URL.", URL_FILE)
        return

    urls = read_queue()
    if not urls:
        logger.warning("File %s kosong. Masukkan link terlebih dahulu.", URL_FILE)
        return

    logger.info("Ada %s URL di antrean.", len(urls))
    media = MediaHandler()
    is_headless = get_headless_choice()
    ytdlp_format = media.get_resolution_format()
    original_count = len(urls)
    pending = set(urls)

    logger.info("Menjalankan hingga %s unduhan sekaligus.", MAX_CONCURRENT_DOWNLOADS)
    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)
    try:
        futures = {
            executor.submit(process_url, url, media, ytdlp_format, is_headless): url
            for url in urls
        }

        for completed_count, future in enumerate(as_completed(futures), start=1):
            target_url = futures[future]
            try:
                success, title = future.result()
            except Exception:
                logger.exception("[%s] Worker gagal secara tak terduga.", target_url)
                success, title = False, "Video_Unduhan_Otomatis"

            if success:
                pending.remove(target_url)
                save_queue([url for url in urls if url in pending])
                logger.info("Selesai (%s/%s); URL dihapus dari antrean: %s", completed_count, original_count, target_url)
                notify_complete(title)
            else:
                logger.error("[%s] Gagal. URL tetap tersimpan untuk dicoba lagi.", target_url)

        logger.info("Antrean selesai. Sisa URL: %s.", len(pending))
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Menerima sinyal pembatalan (Ctrl+C). Menghentikan semua proses unduhan...[/bold yellow]")
        media.terminate_all()
        for b in list(active_browsers):
            try:
                b.close()
            except Exception:
                pass
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    finally:
        executor.shutdown(wait=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Program berhasil dihentikan. URL yang belum selesai tetap tersimpan di antrean.[/bold yellow]")
        os._exit(0)
