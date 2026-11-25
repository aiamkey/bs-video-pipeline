"""cosyvoice-v2 按章节合成 + 轻削静音（保留停顿）→ 配音与时间轴。

用法：
  set DASHSCOPE_API_KEY=sk-xxx
  python tools\\cosy_chapter.py script-bs.json voice-bs-cheng longcheng_v2 1.5 0.5
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import dashscope
import numpy as np
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

ROOT = Path(r"C:\Users\张宇\OneDrive\Desktop\video\lbr-promo")
TMP = Path(r"C:\Users\张宇\OneDrive\Desktop\video\qa2\tts-cosy")
FFMPEG = "E:/miniconda/envs/JupyterProject/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v9.0.2.exe"
SR = 24000
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]


def tts(text: str, voice: str, rate: float) -> bytes:
    synth = SpeechSynthesizer(model="cosyvoice-v2", voice=voice, format=AudioFormat.MP3_24000HZ_MONO_256KBPS, speech_rate=rate)
    audio = synth.call(text)
    if not audio:
        raise RuntimeError(str(synth.get_response()))
    return audio


def to_wav(src: Path, dst: Path) -> np.ndarray:
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)
    with wave.open(str(dst)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def main() -> None:
    script_name, name = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "longcheng_v2"
    rate = float(sys.argv[4]) if len(sys.argv) > 4 else 1.5
    gap = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
    silence = float(sys.argv[6]) if len(sys.argv) > 6 else 0.30

    script = json.loads((ROOT / "scripts" / script_name).read_text(encoding="utf-8-sig"))
    TMP.mkdir(parents=True, exist_ok=True)
    pieces = []
    for i, ch in enumerate(script["chapters"]):
        text = "".join(t["text"] if t["text"][-1] in "。！？" else t["text"] + "。" for t in ch["lines"])
        mp3 = TMP / f"ch{i:02d}.mp3"
        mp3.write_bytes(tts(text, voice, rate))
        data = to_wav(mp3, TMP / f"ch{i:02d}.wav")
        pieces.append(data)
        pieces.append(np.zeros(int(gap * SR), dtype=np.float32))
        print(f"ch{i:02d} {len(data)/SR:6.2f}s")

    out = np.concatenate(pieces)
    raw = TMP / f"{name}-raw.wav"
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())

    dst = ROOT / "public" / "audio" / f"{name}.wav"
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", str(raw),
         "-af", f"silenceremove=start_periods=0:stop_periods=-1:stop_duration={silence}:stop_threshold=-42dB,acompressor=threshold=-19dB:ratio=2.6:attack=5:release=130:makeup=1.3",
         "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )
    with wave.open(str(dst)) as w:
        print(f"-> {dst.name}  {w.getnframes()/w.getframerate():.1f}s")


main()
