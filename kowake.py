# kowake.py – 非同期構成向け：Blob URL → テキスト整形処理

import os
import platform
import shutil

# ── 1) ffmpeg / ffprobe パス検出 ───────────────────────────────
# まず環境変数から
ffmpeg_path = os.getenv("FFMPEG_PATH")
ffprobe_path = os.getenv("FFPROBE_PATH")

# 環境変数がなければプロジェクト内のバイナリを探す
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

# それでも見つからなければシステムPATHを検索
if not os.path.isfile(ffmpeg_path):
    ffmpeg_path = shutil.which("ffmpeg") or ffmpeg_path
if not os.path.isfile(ffprobe_path):
    ffprobe_path = shutil.which("ffprobe") or ffprobe_path

# ── 2) 環境変数と PATH に設定 ─────────────────────────────────
os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BINARY"]  = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path

# ── 3) pydub に反映 ─────────────────────────────────────────────
from pydub import AudioSegment
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe  = ffprobe_path

print(f"[INFO] Using ffmpeg:  {ffmpeg_path}")
print(f"[INFO] Using ffprobe: {ffprobe_path}")
print(f"[INFO] PATH begins with: {os.environ['PATH'].split(os.pathsep)[0]}")

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

async def transcribe_and_correct(audio_blob_url: str) -> str:
    print(f"[DEBUG] transcribe_and_correct({audio_blob_url})")

    # URL を安全に再構成
    parsed    = urlparse(audio_blob_url)
    safe_path = "/".join(quote(p) for p in parsed.path.split("/"))
    safe_url  = f"{parsed.scheme}://{parsed.netloc}{safe_path}"
    if parsed.query:
        safe_url += f"?{parsed.query}"
    audio_blob_url = safe_url

    # ダウンロード → 一時保存
    local_audio_path = "temp_audio" + os.path.splitext(parsed.path)[1]  # 拡張子保持
    download_blob(audio_blob_url, local_audio_path)

    # 分割と並列実行
    audio = AudioSegment.from_file(local_audio_path,
                                   format=os.path.splitext(local_audio_path)[1][1:])  # 'm4a'→mp4
    chunk_ms  = 10 * 60 * 1000
    chunks    = [audio[i:i + chunk_ms] for i in range(0, len(audio), chunk_ms)]

    corrected = []
    batch_size = 6
    for b in range(0, len(chunks), batch_size):
        partials = await asyncio.gather(*[
            _transcribe_chunk(idx + b, c) for idx, c in enumerate(chunks[b:b + batch_size])
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
    return _apply_keyword_replacements(full_text)

# …（以降キーワード管理や Blob 保存部分はそのまま）

# ─── キーワード管理 ───────────────────────────────────────────
_KEYWORDS_DB   = []
BLOB_JSON_PATH = "settings/keywords.json"
LOCAL_TEMP_JSON = "temp_keywords.json"

def get_all_keywords():
    return _KEYWORDS_DB

def get_keyword_by_id(keyword_id):
    for k in _KEYWORDS_DB:
        if k["id"] == keyword_id:
            return k
    return None

def add_keyword(reading, wrong_examples, keyword):
    _KEYWORDS_DB.append({
        "id": str(uuid.uuid4()),
        "reading": reading,
        "wrong_examples": wrong_examples,
        "keyword": keyword,
    })
    _save_keywords_to_blob()

def delete_keyword_by_id(keyword_id):
    global _KEYWORDS_DB
    _KEYWORDS_DB = [k for k in _KEYWORDS_DB if k["id"] != keyword_id]
    _save_keywords_to_blob()

def update_keyword_by_id(keyword_id, reading, wrong_examples, keyword):
    for k in _KEYWORDS_DB:
        if k["id"] == keyword_id:
            k.update(reading=reading, wrong_examples=wrong_examples, keyword=keyword)
            break
    _save_keywords_to_blob()

def _apply_keyword_replacements(text: str) -> str:
    for kw in _KEYWORDS_DB:
        correct = kw["keyword"]
        targets = [kw["reading"]] + [
            e.strip() for e in kw.get("wrong_examples", "").split(",") if e.strip()
        ]
        for tgt in targets:
            text = re.sub(re.escape(tgt), correct, text)
    return text

# ─── Blob 連携 ────────────────────────────────────────────────
def load_keywords_from_file():
    global _KEYWORDS_DB
    try:
        Path(LOCAL_TEMP_JSON).parent.mkdir(parents=True, exist_ok=True)
        download_blob(BLOB_JSON_PATH, LOCAL_TEMP_JSON)
        with open(LOCAL_TEMP_JSON, encoding="utf-8") as f:
            _KEYWORDS_DB = json.load(f)
        print(f"[INFO] キーワード {len(_KEYWORDS_DB)} 件を Azure からロードしました")
    except Exception as e:
        print(f"[WARN] キーワード読込失敗: {e}")
        _KEYWORDS_DB = []

def _save_keywords_to_blob():
    try:
        with open(LOCAL_TEMP_JSON, "w", encoding="utf-8") as f:
            json.dump(_KEYWORDS_DB, f, ensure_ascii=False, indent=2)
        with open(LOCAL_TEMP_JSON, "rb") as f:
            upload_to_blob(BLOB_JSON_PATH, f)
        print("[INFO] キーワードを Azure へ保存しました")
    except Exception as e:
        print(f"[ERROR] キーワード保存失敗: {e}")
