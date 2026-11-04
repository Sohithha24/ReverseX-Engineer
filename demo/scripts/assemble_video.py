"""Assemble scene WebMs + narration into 1080p H.264 MP4 with burned-in subtitles."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
RAW = DEMO / "raw"
AUDIO = DEMO / "audio"
WORK = DEMO / "work"
FFMPEG = ROOT / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v9.0.2.exe"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd[:8]), "…")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-4000:])
        raise RuntimeError(f"Command failed: {cmd[0]}")


def ffprobe_duration(path: Path) -> float:
    # Prefer ffprobe from same package dir if present; else parse ffmpeg -i
    cmd = [
        str(FFMPEG),
        "-i",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Duration: HH:MM:SS.xx in stderr
    for line in (proc.stderr or "").splitlines():
        if "Duration:" in line:
            part = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = part.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not probe duration for {path}")


def make_scene_clip(scene: dict) -> Path:
    sid = scene["id"]
    video_in = RAW / f"{sid}.webm"
    audio_in = DEMO / scene["audio_wav"]
    target = float(scene["duration"])
    out = WORK / f"{sid}.mp4"
    if not video_in.exists():
        raise FileNotFoundError(video_in)
    # Scale/pad to 1920x1080, set fps 30, force duration to match audio (trim or freeze last frame)
    # Use -t on output equal to audio duration; if video shorter, tpad freeze
    vdur = ffprobe_duration(video_in)
    filters = [
        "scale=1920:1080:force_original_aspect_ratio=decrease",
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "fps=30",
        "format=yuv420p",
    ]
    if vdur < target - 0.05:
        pad_sec = target - vdur + 0.05
        filters.append(f"tpad=stop_mode=clone:stop_duration={pad_sec:.3f}")
    vf = ",".join(filters)
    run(
        [
            str(FFMPEG),
            "-y",
            "-i",
            str(video_in),
            "-i",
            str(audio_in),
            "-vf",
            vf,
            "-t",
            f"{target:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )
    return out


def concat_clips(clips: list[Path], out: Path) -> None:
    list_file = WORK / "concat.txt"
    # Re-encode concat with short crossfade-free joins; insert 0.35s black+silence between via generated pads
    parts: list[Path] = []
    for i, clip in enumerate(clips):
        parts.append(clip)
        if i < len(clips) - 1:
            pad = WORK / f"pad_{i}.mp4"
            run(
                [
                    str(FFMPEG),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=0xF7F4EF:s=1920x1080:d=0.35",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                    "-c:v",
                    "libx264",
                    "-t",
                    "0.35",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(pad),
                ]
            )
            parts.append(pad)
    lines = [f"file '{p.resolve().as_posix()}'" for p in parts]
    list_file.write_text("\n".join(lines), encoding="utf-8")
    run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out),
        ]
    )


def burn_subtitles(video: Path, srt: Path, out: Path) -> None:
    # Escape path for ffmpeg subtitles filter on Windows
    srt_escaped = srt.resolve().as_posix().replace(":", "\\:")
    style = (
        "FontName=Segoe UI,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00111111,"
        "BorderStyle=3,Outline=2,Shadow=0,MarginV=48,Alignment=2"
    )
    vf = f"subtitles='{srt_escaped}':force_style='{style}'"
    run(
        [
            str(FFMPEG),
            "-y",
            "-i",
            str(video),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((AUDIO / "timeline.json").read_text(encoding="utf-8"))
    clips = []
    for scene in timeline["scenes"]:
        print(f"Assemble {scene['id']}…")
        clips.append(make_scene_clip(scene))
    joined = WORK / "joined.mp4"
    concat_clips(clips, joined)
    final = DEMO / "reversex_demo.mp4"
    srt = DEMO / "demo_subtitles.srt"
    burn_subtitles(joined, srt, final)
    dur = ffprobe_duration(final)
    meta = {
        "output": str(final),
        "duration_seconds": round(dur, 3),
        "scenes": len(clips),
        "resolution": "1920x1080",
        "video_codec": "h264",
        "audio_codec": "aac",
        "subtitles": "burned-in + demo_subtitles.srt",
    }
    (DEMO / "assembly_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
