# ffmpeg_tools.py
"""
Async ffmpeg utility functions used by main.py
Each function runs ffmpeg in a subprocess and raises on failure.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Optional

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
TMP_DIR = Path(os.getenv("TMP_DIR", "downloads"))
TMP_DIR.mkdir(exist_ok=True, parents=True)

async def _run_cmd(cmd: List[str], timeout: Optional[int] = 600) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("ffmpeg command timed out")
    if proc.returncode != 0:
        out = stdout.decode(errors="ignore")
        err = stderr.decode(errors="ignore")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstdout: {out}\nstderr: {err}")

# --- Individual operations ---

async def compress_video(input_path: str, output_path: str, crf: int = 23, preset: str = "fast"):
    """
    Re-encode video with libx264 and given crf.
    """
    cmd = [
        FFMPEG, "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    await _run_cmd(cmd)
    return output_path

async def merge_videos(input_paths: List[str], output_path: str, crf: int = 23):
    """
    Concatenate videos using ffmpeg concat demuxer with re-encoding (robust across codecs).
    """
    list_file = TMP_DIR / f"concat_{Path(output_path).stem}_{os.getpid()}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in input_paths:
            f.write(f"file '{Path(p).resolve()}'\n")
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    try:
        await _run_cmd(cmd)
        return output_path
    finally:
        try:
            list_file.unlink()
        except Exception:
            pass

async def add_text_watermark(input_path: str, output_path: str, text: str = "Watermark",
                             color: str = "white", fontsize: int = 36, position: str = "center"):
    """
    Adds a static text watermark. position: 'center' or 'top-left', 'top-right', 'bottom-left', 'bottom-right'
    """
    # Determine drawtext x/y
    pos = position.lower()
    if pos == "center":
        x = "(w-text_w)/2"
        y = "(h-text_h)/2"
    elif pos == "top-left":
        x, y = "10", "10"
    elif pos == "top-right":
        x, y = "w-text_w-10", "10"
    elif pos == "bottom-left":
        x, y = "10", "h-text_h-10"
    else:  # bottom-right
        x, y = "w-text_w-10", "h-text_h-10"

    # Use fontfile env var if available
    fontfile = os.getenv("FONT_FILE")  # optional path to .ttf
    drawtext = f"drawtext=text='{text}':fontcolor={color}:fontsize={fontsize}:x={x}:y={y}"
    if fontfile:
        drawtext += f":fontfile={fontfile}"

    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", drawtext, "-c:a", "copy", output_path]
    await _run_cmd(cmd)
    return output_path

async def add_moving_watermark(input_path: str, output_path: str, text: str = "Watermark", mode: str = "left-right"):
    """
    Adds a simple animated watermark moving across screen.
    mode: 'left-right' or 'top-bottom'
    """
    fontfile = os.getenv("FONT_FILE")
    fontsize = int(os.getenv("WM_FONT_SIZE", "36"))
    color = os.getenv("WM_COLOR", "white")
    if mode == "top-bottom":
        # y moves from -text_h to h
        expr = f"drawtext=text='{text}':fontcolor={color}:fontsize={fontsize}:x=(w-text_w)/2:y=-text_h+mod(t*(h+text_h)/max(1,10),h+text_h)"
    else:
        # left-right default: x moves from -text_w to w
        expr = f"drawtext=text='{text}':fontcolor={color}:fontsize={fontsize}:x=-text_w+mod(t*(w+text_w)/max(1,10),w+text_w):y=(h-text_h)/2"
    if fontfile:
        expr += f":fontfile={fontfile}"
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", expr, "-c:a", "copy", output_path]
    await _run_cmd(cmd)
    return output_path

async def trim_video(input_path: str, output_path: str, start: str, end: str):
    """
    Trim using -ss and -to
    """
    cmd = [FFMPEG, "-y", "-i", input_path, "-ss", start, "-to", end, "-c", "copy", output_path]
    # If copy fails (due to keyframe issues), fall back to reencode:
    try:
        await _run_cmd(cmd)
    except RuntimeError:
        cmd = [FFMPEG, "-y", "-i", input_path, "-ss", start, "-to", end, "-c:v", "libx264", "-c:a", "aac", output_path]
        await _run_cmd(cmd)
    return output_path

async def resize_video(input_path: str, output_path: str, height: int):
    """
    Resize keeping aspect ratio: scale=-2:height
    """
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", f"scale=-2:{height}", "-c:v", "libx264", "-c:a", "aac", output_path]
    await _run_cmd(cmd)
    return output_path

async def extract_audio(input_path: str, output_path: str):
    cmd = [FFMPEG, "-y", "-i", input_path, "-vn", "-acodec", "mp3", "-ab", "192k", output_path]
    await _run_cmd(cmd)
    return output_path

async def extract_thumbnail(input_path: str, output_path: str, at_time: str = "00:00:03"):
    cmd = [FFMPEG, "-y", "-ss", at_time, "-i", input_path, "-frames:v", "1", output_path]
    await _run_cmd(cmd)
    return output_path

async def replace_audio(video_path: str, audio_path: str, output_path: str):
    cmd = [FFMPEG, "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_path]
    # If audio codec not compatible, re-encode audio
    try:
        await _run_cmd(cmd)
    except RuntimeError:
        cmd = [FFMPEG, "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_path]
        await _run_cmd(cmd)
    return output_path

async def change_speed(input_path: str, output_path: str, factor: float):
    """
    Change playback speed.
    For video: setpts=PTS/<factor> ; for audio: atempo supports 0.5-2.0 increments (chain if needed)
    """
    # Video filter
    setpts = f"setpts=PTS/{factor}"
    # Handle audio atempo: chain if factor out of range
    atempo_filters = []
    # ffmpeg atempo supports 0.5-2.0 per filter; break factor accordingly for audio filter
    remaining = factor
    if remaining <= 0:
        raise ValueError("Speed factor must be > 0")
    while remaining > 2.0:
        atempo_filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        atempo_filters.append("atempo=0.5")
        remaining *= 2.0
    atempo_filters.append(f"atempo={remaining}")
    atempo = ",".join(atempo_filters)
    vf = setpts
    af = atempo
    cmd = [FFMPEG, "-y", "-i", input_path, "-filter_complex", f"[0:v] {vf} [v]; [0:a] {af} [a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", output_path]
    await _run_cmd(cmd)
    return output_path

async def rotate_video(input_path: str, output_path: str, degrees: int):
    """
    Rotate by 90, 180, 270 degrees using transpose or rotate filter
    """
    if degrees not in (90, 180, 270):
        raise ValueError("Degrees must be 90, 180, or 270")
    if degrees == 90:
        vf = "transpose=1"
    elif degrees == 270:
        vf = "transpose=2"
    else:  # 180
        vf = "transpose=1,transpose=1"
    cmd = [FFMPEG, "-y", "-i", input_path, "-vf", vf, "-c:v", "libx264", "-c:a", "copy", output_path]
    await _run_cmd(cmd)
    return output_path
