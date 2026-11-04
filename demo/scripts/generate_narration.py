"""Generate scene narration WAVs/MP3s via edge-tts and build a timed SRT."""
from __future__ import annotations

import asyncio
import json
import subprocess
import wave
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
AUDIO = DEMO / "audio"
FFMPEG = ROOT / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v9.0.2.exe"
VOICE = "en-US-JennyNeural"
RATE = "+0%"

SCENES = [
    {
        "id": "01_intro",
        "title": "Introduction",
        "text": (
            "ReverseX Engineer is an AI-powered software investigation platform that explores "
            "how application features behave, reconstructs them, and independently verifies the results. "
            "It works against authorized local demo applications—not arbitrary websites on the open internet. "
            "This short walkthrough uses verified local results from a completed Guided Demo."
        ),
    },
    {
        "id": "02_investigation",
        "title": "AI Investigation",
        "text": (
            "A user selects an allowlisted application—here, TaskBoard—and chooses Understand and Reconstruct. "
            "For this demonstration we open a Guided Demo investigation that was already completed and verified, "
            "rather than starting a new live Meta Muse run during recording. "
            "In Muse mode, the agent can choose browser interactions such as fill, click, and reload, "
            "while ReverseX records observations into an evidence-backed behavioral specification. "
            "The job on screen ran in Guided Demo mode with zero Meta API requests in that release pass, "
            "so you can trust the stages without paying for a fresh Muse investigation."
        ),
    },
    {
        "id": "03_reconstruction",
        "title": "Feature Reconstruction",
        "text": (
            "From the frozen behavior specification, ReverseX produces an independent implementation as static files—"
            "HTML, JavaScript, and CSS. The original TaskBoard source never enters the model context. "
            "In this verified run, reconstruction was reused from an existing Phase Two artifact. "
            "We are therefore showing prior reconstruction evidence and status labels from that completed job, "
            "not implying that new reconstruction files were generated live during this video recording."
        ),
    },
    {
        "id": "04_validation",
        "title": "Independent Validation",
        "text": (
            "ReverseX then compares the original application with the reconstruction using independent behavioral tests. "
            "Playwright exercises holdout scenarios against both sides so the model does not grade itself. "
            "For TaskBoard, five of five scenarios passed—a one hundred percent match on the tested cases. "
            "That score applies to those scenarios, not every possible behavior of the application."
        ),
    },
    {
        "id": "05_reports",
        "title": "Simple and Developer Reports",
        "text": (
            "The Simple Report explains the investigation in plain language for nontechnical readers—"
            "what was tested, what matched, and key limits. "
            "Switching to the Developer Report keeps the same verified findings, "
            "and adds technical observations, stage details, and testing evidence. "
            "Both reports draw from one completed investigation record, so the story stays consistent."
        ),
    },
    {
        "id": "06_repair",
        "title": "Controlled AI Repair",
        "text": (
            "Next is the Controlled Repair Example—a labeled fault-injection evaluation. "
            "A deliberate defect was introduced into a reconstruction copy, detected by the oracle, "
            "then corrected through a bounded repair attempt and revalidated. "
            "This is separate from the TaskBoard investigation you just reviewed, "
            "and it is not an organic AI failure from that completed job."
        ),
    },
    {
        "id": "07_conclusion",
        "title": "Conclusion",
        "text": (
            "ReverseX demonstrates investigate, reconstruct, independently validate, and controlled repair—"
            "with evidence you can audit. ReverseX Engineer."
        ),
    },
]


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_cues(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    """Split scene text into subtitle cues by sentence, timed across [start, end]."""
    parts = []
    buf = text.strip()
    for sep in (". ", "? ", "! "):
        pass
    # Simple sentence split keeping punctuation
    sentences: list[str] = []
    current = ""
    for ch in text.strip():
        current += ch
        if ch in ".?!" and len(current.strip()) > 8:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    if not sentences:
        return [(start, end, text.strip())]
    weights = [max(len(s), 1) for s in sentences]
    total_w = sum(weights)
    duration = max(end - start, 0.1)
    cues = []
    t = start
    for i, (sent, w) in enumerate(zip(sentences, weights)):
        slice_dur = duration * (w / total_w)
        t2 = end if i == len(sentences) - 1 else t + slice_dur
        cues.append((t, t2, sent))
        t = t2
    return cues


async def synthesize_scene(scene: dict, out_mp3: Path) -> None:
    communicate = edge_tts.Communicate(scene["text"], VOICE, rate=RATE)
    await communicate.save(str(out_mp3))


def mp3_to_wav(mp3: Path, wav: Path) -> None:
    cmd = [
        str(FFMPEG),
        "-y",
        "-i",
        str(mp3),
        "-ac",
        "1",
        "-ar",
        "24000",
        str(wav),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


async def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    timeline = []
    cursor = 0.0
    all_cues: list[tuple[float, float, str]] = []

    for scene in SCENES:
        mp3 = AUDIO / f"{scene['id']}.mp3"
        wav = AUDIO / f"{scene['id']}.wav"
        print(f"TTS {scene['id']}…")
        await synthesize_scene(scene, mp3)
        mp3_to_wav(mp3, wav)
        dur = wav_duration(wav)
        # Small breathing room between scenes in the final timeline
        pad = 0.35
        start = cursor
        end = cursor + dur
        timeline.append(
            {
                "id": scene["id"],
                "title": scene["title"],
                "text": scene["text"],
                "audio_mp3": str(mp3.relative_to(DEMO)).replace("\\", "/"),
                "audio_wav": str(wav.relative_to(DEMO)).replace("\\", "/"),
                "duration": round(dur, 3),
                "start": round(start, 3),
                "end": round(end, 3),
            }
        )
        all_cues.extend(split_cues(scene["text"], start, end))
        cursor = end + pad
        print(f"  {dur:.2f}s")

    # Concatenate full narration wav
    full_wav = AUDIO / "narration_full.wav"
    # Use ffmpeg concat demuxer
    list_file = AUDIO / "concat_list.txt"
    lines = []
    for item in timeline:
        wav_path = (DEMO / item["audio_wav"]).resolve()
        # After each scene, insert a short silence via anext filter is harder;
        # bake pad into concat by generating silence files.
        lines.append(f"file '{wav_path.as_posix()}'")
        silence = AUDIO / f"_silence_{item['id']}.wav"
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=24000:cl=mono",
                "-t",
                "0.35",
                str(silence),
            ],
            check=True,
            capture_output=True,
        )
        lines.append(f"file '{silence.as_posix()}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
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
            str(full_wav),
        ],
        check=True,
        capture_output=True,
    )
    full_mp3 = AUDIO / "narration_full.mp3"
    subprocess.run(
        [str(FFMPEG), "-y", "-i", str(full_wav), "-codec:a", "libmp3lame", "-q:a", "2", str(full_mp3)],
        check=True,
        capture_output=True,
    )

    srt_path = DEMO / "demo_subtitles.srt"
    with srt_path.open("w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(all_cues, 1):
            f.write(f"{i}\n{srt_ts(a)} --> {srt_ts(b)}\n{text}\n\n")

    meta = {
        "voice": VOICE,
        "rate": RATE,
        "total_duration_with_pads": round(cursor, 3),
        "scenes": timeline,
    }
    (AUDIO / "timeline.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({"total": cursor, "scenes": len(timeline), "srt": str(srt_path)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
