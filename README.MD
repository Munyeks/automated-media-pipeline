# Private Video Downloader

Downloader antrean berbasis Python dengan yt-dlp sebagai extractor utama. Untuk halaman yang tidak dikenali yt-dlp, browser Chromium dapat mencari playlist HLS atau file video yang dimuat langsung oleh halaman.

## Fitur

- Mendukung situs yang dikenali yt-dlp serta URL media langsung yang kompatibel.
- Antrean `urls.txt` tetap berisi URL yang gagal dan diperbarui secara atomik saat unduhan berhasil.
- Menghapus URL duplikat dalam satu antrean.
- Memilih kualitas maksimum, melanjutkan unduhan parsial, dan menghindari menimpa file yang sudah ada.
- Mengunduh satu URL sekaligus secara default untuk menjaga kestabilan; batas worker dapat diatur sampai 4.
- Batas kecepatan dapat dimatikan untuk memakai kapasitas koneksi yang tersedia.
- Fallback browser memakai sesi baru per URL dan hanya meneruskan header yang memang dikirim untuk request media tersebut.
- Deteksi media otomatis dan langsung lanjut unduh (*early exit*) begitu link media tertangkap.
- Fallback interaktif: browser bisa otomatis muncul sementara jika ada captcha atau tombol play yang butuh diklik manual.
- Dukungan proxy untuk yt-dlp dan browser (berguna jika situs terblokir oleh provider).
- Opsi memakai cookies dari browser lokal untuk situs yang mewajibkan login.
- Tampilan progres unduhan real-time satu baris.
- Menghentikan proses unduhan dan browser secara aman dan instan saat menekan `Ctrl+C`.
- Tidak menganggap potongan `.ts` sebagai video utuh.

Dukungan situs bergantung pada extractor yt-dlp dan cara situs menyediakan medianya. DRM, pembatasan akses, dan situs yang tidak didukung tidak dilewati.

## Menjalankan

1. Siapkan environment Python, lalu pasang dependensi:

   ```powershell
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Masukkan URL yang dapat diakses ke `urls.txt`, satu URL per baris.
3. Jalankan:

   ```powershell
   python main.py
   ```

URL yang berhasil akan dihapus dari `urls.txt`. URL yang gagal tetap ada agar dapat dicoba lagi pada eksekusi berikutnya. File media disimpan di folder `downloads` secara default.

## Konfigurasi

Kualitas dipilih saat aplikasi berjalan. Salin `.env.example` menjadi `.env` untuk mengatur konfigurasi unduhan:

- `URL_FILE` dan `DOWNLOAD_DIR`: Lokasi file antrean URL dan folder hasil unduhan.
- `TIMEOUT_MS` dan `SCAN_TIMEOUT_SEC`: Waktu tunggu pemuatan halaman dan batas waktu pemindaian media.
- `MAX_RETRIES` dan `RETRY_DELAY_SEC`: Jumlah percobaan ulang dan jeda waktu jika unduhan gagal.
- `DOWNLOAD_LIMIT_RATE`: Batas kecepatan unduh (kosongkan untuk kecepatan penuh, atau isi misal `2M`).
- `CONCURRENT_FRAGMENTS`: Jumlah koneksi paralel fragmen video (default `8`).
- `MAX_CONCURRENT_DOWNLOADS`: Jumlah URL yang diunduh bersamaan (default `1`, maksimal `4`).
- `BROWSER_COOKIES`: Nama browser (misal `chrome`, `edge`, `firefox`) jika ingin memakai sesi login untuk video private.
- `ENABLE_INTERACTIVE_FALLBACK`: Buka browser visual jika video belum terdeteksi di latar belakang (`true`/`false`).
- `INTERACTIVE_TIMEOUT_SEC`: Batas waktu menunggu kamu menyelesaikan captcha/klik play manual (default `60` detik).
- `PROXY`: Alamat proxy jika koneksi ke situs diblokir provider (contoh: `http://127.0.0.1:7890` atau `socks5://127.0.0.1:1080`).

Jangan membagikan file `.env` jika berisi konfigurasi pribadi atau akun.
