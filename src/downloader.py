import tempfile
from pathlib import Path
import yt_dlp

MAX_FILESIZE_MB = 45  # margem abaixo do limite de 50MB do Telegram


def download(url: str) -> Path | None:
    tmp_dir = Path(tempfile.mkdtemp())
    out_template = str(tmp_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": (
            "bestvideo[ext=mp4][filesize<?47M]+bestaudio[ext=m4a]"
            "/best[ext=mp4][filesize<?47M]"
            "/best[filesize<?47M]"
            "/best"
        ),
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "max_filesize": MAX_FILESIZE_MB * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            path = Path(filename)
            if not path.exists():
                # yt-dlp pode ter trocado a extensão após merge
                for f in tmp_dir.iterdir():
                    if f.suffix in (".mp4", ".webm", ".mkv"):
                        path = f
                        break

            if path.exists() and path.stat().st_size <= MAX_FILESIZE_MB * 1024 * 1024:
                return path
            return None
    except Exception as e:
        print(f"[downloader] erro: {e}")
        return None
