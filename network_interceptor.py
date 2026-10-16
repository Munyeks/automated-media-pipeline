import re
from urllib.parse import urlparse

from config import logger, TIMEOUT_MS, SCAN_TIMEOUT_SEC


class NetworkInterceptor:
    """Find openly requested media URLs on a page.

    This is a compatibility fallback for pages yt-dlp cannot inspect directly.
    It does not click through gates, alter browser identity, or inspect DRM keys.
    """

    MEDIA_EXTENSIONS = (".m3u8", ".mp4", ".webm", ".mov", ".m4v", ".mpd")

    def extract_link(
        self,
        context,
        target_url: str,
        is_interactive: bool = False,
        interactive_timeout_sec: int = 60,
    ) -> tuple:
        mode_desc = "mode interaktif" if is_interactive else "mode otomatis"
        logger.info("Memeriksa media yang dimuat halaman (%s): %s", mode_desc, target_url)
        candidates = []
        page_title = "Video_Unduhan_Otomatis"
        page = context.new_page()

        def is_hls_or_video(url: str, content_type: str = "") -> tuple[bool, bool]:
            path = urlparse(url).path.lower()
            # Abaikan potongan fragmen .ts
            if path.endswith(".ts") or "video/mp2t" in content_type:
                return False, False

            is_m3u8 = (
                path.endswith((".m3u8", ".mpd"))
                or ".m3u8" in url.lower()
                or ".mpd" in url.lower()
                or any(ct in content_type for ct in ["application/vnd.apple.mpegurl", "application/x-mpegurl", "application/dash+xml"])
            )
            is_video = (
                path.endswith(self.MEDIA_EXTENSIONS[1:])
                or any(ct in content_type for ct in ["video/mp4", "video/webm", "video/quicktime"])
            )
            return is_m3u8, is_video

        def capture_request(request):
            try:
                url = request.url
                is_m3u8, is_video = is_hls_or_video(url)
                if is_m3u8 or is_video:
                    try:
                        request_headers = request.all_headers()
                    except Exception:
                        request_headers = {}
                    if not any(c[0] == url for c in candidates):
                        candidates.append((url, request_headers))
            except Exception:
                pass

        def capture_response(response):
            try:
                url = response.url
                content_type = response.headers.get("content-type", "").lower()
                is_m3u8, is_video = is_hls_or_video(url, content_type)
                if is_m3u8 or is_video:
                    try:
                        request_headers = response.request.all_headers()
                    except Exception:
                        request_headers = {}
                    if not any(c[0] == url for c in candidates):
                        candidates.append((url, request_headers))
            except Exception:
                pass

        page.on("request", capture_request)
        page.on("response", capture_response)

        def attempt_autoplay():
            try:
                page.evaluate("""() => {
                    // Coba jalankan video yang ada di DOM
                    document.querySelectorAll('video').forEach(v => {
                        try {
                            v.muted = true;
                            v.play();
                        } catch(e) {}
                    });
                    // Coba klik tombol play umum
                    const selectors = [
                        'button[class*="play" i]',
                        'div[class*="play" i]',
                        '.vjs-big-play-button',
                        '.plyr__control--overlaid',
                        '[aria-label*="Play" i]',
                        '[title*="Play" i]',
                        '.jw-display-icon-display',
                        '.art-control-play'
                    ];
                    for (const s of selectors) {
                        const btn = document.querySelector(s);
                        if (btn) {
                            try { btn.click(); } catch(e) {}
                        }
                    }
                }""")
            except Exception:
                pass

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            raw_title = page.title()
            if raw_title:
                page_title = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", raw_title).strip()

            page.wait_for_timeout(1000)
            attempt_autoplay()

            max_wait = interactive_timeout_sec if is_interactive else max(0, min(SCAN_TIMEOUT_SEC, 30))
            for second in range(max_wait):
                has_playlist = any(
                    urlparse(c[0]).path.lower().endswith((".m3u8", ".mpd")) or ".m3u8" in c[0].lower()
                    for c in candidates
                )
                if has_playlist:
                    logger.info("Playlist media terdeteksi. Menghentikan pemantauan browser.")
                    break

                if candidates and second >= 3:
                    logger.info("Media terdeteksi. Menghentikan pemantauan browser.")
                    break

                if not is_interactive and second % 3 == 0:
                    attempt_autoplay()

                page.wait_for_timeout(1000)
        except Exception as exc:
            logger.info("Pemeriksaan halaman selesai dengan catatan: %s", exc)
        finally:
            page.close()

        # Pilih kandidat terbaik: utamakan m3u8
        selected = next(
            (item for item in candidates if urlparse(item[0]).path.lower().endswith(".m3u8") or ".m3u8" in item[0].lower()),
            None,
        )
        if selected is None:
            selected = next(
                (item for item in candidates if urlparse(item[0]).path.lower().endswith(self.MEDIA_EXTENSIONS[1:])),
                None,
            )
        if selected is None and candidates:
            selected = candidates[0]

        if selected is None:
            return None, page_title, {}

        media_url, request_headers = selected
        headers = {
            key: request_headers[key]
            for key in ("user-agent", "referer", "origin", "cookie")
            if request_headers.get(key)
        }
        logger.info("Media yang dapat diakses ditemukan (%s).", urlparse(media_url).path.rsplit("/", 1)[-1])
        return media_url, page_title or "Video_Unduhan_Otomatis", headers
