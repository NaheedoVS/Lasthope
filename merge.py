# merge.py
# Helpers to merge videos using ffmpeg in a safe async way.

import asyncio
import os
import shlex
from pathlib import Path
from typing import List

# Ensure ffmpeg binary is installed on the host (Heroku buildpack or system)
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
TMP_DIR = Path("downloads")
TMP_DIR.mkdir(exist_ok=True)

async def _run_cmd(cmd: List[str]) -> None:
    """Run subprocess asynchronously, raise on non-zero exit."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with return code {proc.returncode}\n"
            f"stdout: {stdout.decode(errors='ignore')}\n"
            f"stderr: {stderr.decode(errors='ignore')}"
        )

def _ensure_file_list_file(input_paths: List[Path], list_file: Path) -> None:
    """
    Creates a ffmpeg-compatible file list for concat demuxer.
    Each line: file '<path>'
    """
    with list_file.open("w", encoding="utf-8") as f:
        for p in input_paths:
            # ffmpeg requires proper escaping of single quotes; we use absolute paths
            f.write(f"file '{str(p.resolve())}'\n")

async def merge_videos(input_paths: List[str], output_path: str, crf: int = 23) -> str:
    """
    Merge videos by concatenation using ffmpeg demuxer.
    input_paths: list of file paths (already downloaded)
    output_path: final output path
    crf: quality param for re-encoding (lower = better). Keep around 18-28.
    Returns output_path on success.
    """
    if not input_paths or len(input_paths) < 2:
        raise ValueError("Need at least two videos to merge.")

    input_paths = [Path(p) for p in input_paths]
    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")

    TMP_DIR.mkdir(exist_ok=True)
    list_file = TMP_DIR / f"files_{int(asyncio.get_event_loop().time()*1000)}.txt"
    _ensure_file_list_file(input_paths, list_file)

    # Build ffmpeg command:
    # -f concat -safe 0 -i list.txt -c copy out.mp4  (fast but requires same codecs)
    # If codecs differ, re-encode:
    reencode_cmd = [
        FFMPEG_BIN,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]

    try:
        await _run_cmd(reencode_cmd)
        return str(Path(output_path).resolve())
    finally:
        # cleanup
        try:
            if list_file.exists():
                list_file.unlink()
        except Exception:
            pass
            
