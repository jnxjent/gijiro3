import os
import platform
import shutil
import subprocess
import tempfile

# ── 1) ffmpeg / ffprobe パス検出 ───────────────────────────────
import shutil

ffmpeg_path = os.getenv("FFMPEG_PATH")
ffprobe_path = os.getenv("FFPROBE_PATH")

if not (ffmpeg_path and ffprobe_path):
    BASE_DIR = os.path.dirname(__file__)
    BIN_ROOT = os.getenv("FFMPEG_HOME", os.path.join(BASE_DIR, "ffmpeg", "bin"))

    if platform.system() == "Windows":
        tb = os.path.join(BIN_ROOT, "win")
        ffmpeg_path  = os.path.join(tb, "ffmpeg.exe")
        ffprobe_path = os.path.join(tb, "ffprobe.exe")
    else:
        tb = os.path.join(BIN_ROOT, "linux")
        ffmpeg_path  = os.path.join(tb, "ffmpeg")
        ffprobe_path = os.path.join(tb, "ffprobe")

if not os.path.isfile(ffmpeg_path):
    ffmpeg_path = shutil.which("ffmpeg") or ffmpeg_path
if not os.path.isfile(ffprobe_path):
    ffprobe_path = shutil.which("ffprobe") or ffprobe_path

os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BINARY"]  = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path

# ── 2) pydub に反映 ─────────────────────────────────────────────
from pydub import AudioSegment
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe  = ffprobe_path

print(f"[INFO] Using ffmpeg:  {ffmpeg_path}")
print(f"[INFO] Using ffprobe: {ffprobe_path}")

# ── 以下、従来の実装 ────────────────────────────────────────────
import uuid
import re
import json
import asyncio
from pathlib import Path
from urllib.parse import urlparse, quote
from dotenv import load_dotenv
from deepgram import Deepgram
import openai
from storage import upload_to_blob, download_blob

# 環境変数読み込み
load_dotenv()
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE  = os.getenv("OPENAI_API_BASE")
DEPLOYMENT_ID    = os.getenv("DEPLOYMENT_ID")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
TEMPERATURE      = float(os.getenv("TEMPERATURE", 0.7))

openai.api_key     = OPENAI_API_KEY
openai.api_base    = OPENAI_API_BASE
openai.api_type    = "azure"
openai.api_version = "2024-08-01-preview"

deepgram_client = Deepgram(DEEPGRAM_API_KEY)

async def _transcribe_chunk(idx: int, chunk: AudioSegment) -> str:
    tmp_path = f"temp_chunk_{idx}.wav"
    chunk.export(tmp_path, format="wav")
    with open(tmp_path, "rb") as f:
        audio_buf = f.read()
    os.remove(tmp_path)

    response = await deepgram_client.transcription.prerecorded(
        {"buffer": audio_buf, "mimetype": "audio/wav"},
        {
            "model": "nova-2-general",
            "detect_language": True,
            "diarize": True,
            "utterances": True,
        },
    )

    return "\n".join(
        f"[Speaker {u['speaker']}] {u['transcript']}"
        for u in response["results"]["utterances"]
    )

async def transcribe_and_correct(source: str) -> str:
    """
    source が URL なら Blob からダウンロードし、
    ローカルパスなら直接読み込む。
    Fast-Start を適用して moov atom エラーを回避。
    """
    # 1) URL 判定
    if source.lower().startswith("http"):  
        parsed = urlparse(source)
        safe_path = "/".join(quote(p) for p in parsed.path.split("/"))
        safe_url = f"{parsed.scheme}://{parsed.netloc}{safe_path}"
        if parsed.query:
            safe_url += f"?{parsed.query}"
        local_audio = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(parsed.path)[1]).name
        download_blob(safe_url, local_audio)
    else:
        local_audio = source

    # 2) Fast-Start 適用
    ext = os.path.splitext(local_audio)[1]
    fixed_audio = local_audio.replace(ext, f"_fixed{ext}")
    subprocess.run([
        ffmpeg_path, "-y",
        "-i", local_audio,
        "-c", "copy",
        "-movflags", "+faststart",
        fixed_audio
    ], check=True)

    # 3) AudioSegment 読み込み
    audio = AudioSegment.from_file(
        fixed_audio,
        format=ext.lstrip('.')
    )

    # 4) 分割・並列処理
    chunk_ms = 10 * 60 * 1000
    chunks = [audio[i:i + chunk_ms] for i in range(0, len(audio), chunk_ms)]

    corrected = []
    batch_size = 6
    for b in range(0, len(chunks), batch_size):
        partials = await asyncio.gather(*[
            _transcribe_chunk(idx + b, c) 
            for idx, c in enumerate(chunks[b:b + batch_size])
        ])
        for text in partials:
            prompt = (
                "以下の音声書き起こしを自然な日本語にしてください。\n\n"
                f"{text}\n\n"
                "【出力形式】\n"
                "[Speaker X] 発話内容\n"
                "[Speaker X] 発話内容\n"
            )
            res = openai.ChatCompletion.create(
                engine=DEPLOYMENT_ID,
                messages=[
                    {"role": "system", "content": "あなたは日本語整形アシスタントです。"},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0,
                max_tokens=4000,
            )
            corrected.append(res["choices"][0]["message"]["content"])

    full_text = "\n".join(corrected)

    # 5) 後片付け
    if source.lower().startswith("http"):
        os.remove(local_audio)
    os.remove(fixed_audio)

    return _apply_keyword_replacements(full_text)

# ─── キーワード管理以下は変更なし ────────────────────────────────────────────
# （元コードのキーワード管理／Blob 連携部分をそのまま残してください）
