import os
import subprocess
import sys
from rich.prompt import Prompt
from config import (
    logger,
    DOWNLOAD_DIR,
    console,
    DOWNLOAD_LIMIT_RATE,
    CONCURRENT_FRAGMENTS,
    PROGRESS_DELTA_SEC,
    BROWSER_COOKIES,
    PROXY,
)

class MediaHandler:
    def __init__(self):
        self.download_dir = DOWNLOAD_DIR
        self.active_processes = set()
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def terminate_all(self):
        """Hentikan semua proses yt-dlp yang sedang berjalan."""
        for proc in list(self.active_processes):
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
        self.active_processes.clear()

    def get_resolution_format(self) -> str:
        console.print("\n[bold cyan]=== PENGATURAN RESOLUSI MAKSIMAL ===[/bold cyan]")
        console.print("[bold]1.[/bold] Kualitas Terbaik (Mentok Kanan / Default)")
        console.print("[bold]2.[/bold] Maksimal 1080p (FHD)")
        console.print("[bold]3.[/bold] Maksimal 720p (HD)")
        console.print("[bold]4.[/bold] Maksimal 480p (SD)")
        
        # Prompt otomatis memvalidasi input
        pilihan = Prompt.ask("\n[bold yellow]Pilih angka[/bold yellow]", choices=["1", "2", "3", "4"], default="1")
        
        if pilihan == "2": return "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif pilihan == "3": return "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif pilihan == "4": return "bestvideo[height<=480]+bestaudio/best[height<=480]"
        else:
            logger.info("Default dipilih. Menggunakan kualitas terbaik.")
            return "bestvideo+bestaudio/best"

    def download_video(self, url: str, title: str, format_yt: str, headers: dict = None) -> bool:
        display_title = title if title and title != "AUTO" else url
        logger.info("Mulai mengunduh: %s", display_title)

        # Membatasi panjang title dan id agar nama file tidak berantakan (terutama karena token m3u8)
        if title and title != "AUTO":
            import re
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()[:100]
            if not safe_title:
                safe_title = "Video_Unduhan"
            output_template = os.path.join(self.download_dir, f"{safe_title} [%(id).15B].%(ext)s")
        else:
            output_template = os.path.join(self.download_dir, "%(title).100B [%(id).15B].%(ext)s")

        # Run yt-dlp from the active Python environment so the CLI and the
        # installed package cannot silently point at different installations.
        command = [
            sys.executable, "-m", "yt_dlp",
            "-f", format_yt,  
            "--merge-output-format", "mp4",
            "-N", str(CONCURRENT_FRAGMENTS),
            "--windows-filenames",
            "--trim-filenames", "180",
            "--continue",
            "--no-overwrites",
            "-o", output_template,
        ]

        if DOWNLOAD_LIMIT_RATE:
            command.extend(["--limit-rate", DOWNLOAD_LIMIT_RATE])

        if PROXY:
            command.extend(["--proxy", PROXY])

        # Hanya gunakan cookies browser lokal jika belum ada headers dari interceptor
        if BROWSER_COOKIES and not headers:
            command.extend(["--cookies-from-browser", BROWSER_COOKIES])

        if headers:
            for key, value in headers.items():
                if value and key.lower() in ['user-agent', 'referer', 'origin', 'cookie']:
                    command.extend(["--add-header", f"{key}: {value}"])

        command.append(url)

        process = None
        try:
            # Karena proses langsung menulis ke terminal (tanpa di-pipe),
            # yt-dlp bisa menampilkan progress real-time dalam 1 baris (\r).
            process = subprocess.Popen(command)
            self.active_processes.add(process)
            return_code = process.wait()
            if return_code != 0:
                logger.error("yt-dlp gagal (kode %s). URL tetap di antrean untuk dicoba lagi.\n", return_code)
                return False
            logger.info("Selesai mengunduh: %s\n", display_title)
            return True 
        except KeyboardInterrupt:
            if process:
                try:
                    process.terminate()
                    process.kill()
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error(f"Terjadi kesalahan sistem: {e}\n")
            return False
        finally:
            if process and process in self.active_processes:
                self.active_processes.discard(process)
