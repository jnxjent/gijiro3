import os
import json
import base64
import tempfile
import logging
import platform
import subprocess
import uuid
import shutil  # ← NameError 修正で追加
from pathlib import Path

from pydub import AudioSegment
import azure.functions as func

from storage import download_blob, upload_to_blob
from kowake import transcribe_and_correct
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document

# ─── ffmpeg / ffprobe 検出ロジック（ローカル⇆クラウド自動判定） ──────────

FFMPEG_CANDIDATES: list[tuple[str, str]] = []

# ① ENV
ff_env = os.getenv("FFMPEG_PATH")
fp_env = os.getenv("FFPROBE_PATH")
if ff_env and fp_env:
    FFMPEG_CANDIDATES.append((ff_env, fp_env))

# ② リポジトリ同梱
BASE_DIR = Path(__file__).resolve().parent
BIN_ROOT = BASE_DIR / "ffmpeg" / "bin"
if platform.system() == "Windows":
    tb = BIN_ROOT / "win"
    FFMPEG_CANDIDATES.append((str(tb / "ffmpeg.exe"), str(tb / "ffprobe.exe")))
elif platform.system() == "Darwin":
    tb = BIN_ROOT / "mac"
    FFMPEG_CANDIDATES.append((str(tb / "ffmpeg"), str(tb / "ffprobe")))
else:  # Linux
    tb = BIN_ROOT / "linux"
    FFMPEG_CANDIDATES.append((str(tb / "ffmpeg"), str(tb / "ffprobe")))

# ③ PATH
FFMPEG_CANDIDATES.append((shutil.which("ffmpeg") or "", shutil.which("ffprobe") or ""))

# ④ Azure Functions 既定
FFMPEG_CANDIDATES.append(("/home/site/ffmpeg-bin/bin/ffmpeg", "/home/site/ffmpeg-bin/bin/ffprobe"))

ffmpeg_path, ffprobe_path = "", ""
for ff, fp in FFMPEG_CANDIDATES:
    if ff and os.path.isfile(ff) and fp and os.path.isfile(fp):
        ffmpeg_path, ffprobe_path = ff, fp
        break

if not ffmpeg_path:
    raise RuntimeError("FFMPEG/FFPROBE binary not found. Set env vars or include binaries.")

# PATH へ追記し pydub へ反映
os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path
print(f"[INIT] FFMPEG_BINARY  : {ffmpeg_path}")
print(f"[INIT] FFPROBE_BINARY : {ffprobe_path}")

# ─── ロガー設定 ─────────────────────────────────────────────
logger = logging.getLogger("ProcessAudioFunction")
logger.setLevel(logging.INFO)

TMP_DIR = tempfile.gettempdir()  # 一時ディレクトリ


async def main(msg: func.QueueMessage) -> None:
    try:
        # ─── JSON／Base64 自動判定デコード ───────────────────────────
        raw = msg.get_body().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            # Base64 になっている場合はこちらでデコード
            decoded = base64.b64decode(raw).decode("utf-8")
            body = json.loads(decoded)

        job_id = body["job_id"]
        blob_url = body["blob_url"]
        template_blob_url = body["template_blob_url"]
        logger.info(f"Received job {job_id}, blob: {blob_url}, template: {template_blob_url}")

        # 1. 音声を /tmp にダウンロード
        local_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")
        download_blob(blob_url, local_audio)

        # 2. Fast-Start
        fixed_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}_fixed.mp4")
        subprocess.run([
            ffmpeg_path,
            "-y",
            "-i",
            local_audio,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            fixed_audio,
        ], check=True)

        # 3. 文字起こし
        transcript = await transcribe_and_correct(fixed_audio)

        # 4. テンプレート DL
        template_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}_template.docx")
        download_blob(template_blob_url, template_path)

        # 5. 情報抽出 → Word
        meeting_info = await extract_meeting_info_and_speakers(transcript, template_path)
        local_docx = os.path.join(TMP_DIR, f"{job_id}.docx")
        blob_docx = f"processed/{job_id}.docx"
        process_document(template_path, local_docx, meeting_info)

        with open(local_docx, "rb") as fp:
            upload_to_blob(blob_docx, fp, add_audio_prefix=False)
        logger.info(f"Job {job_id} completed, saved to {blob_docx}")

    except Exception:
        logger.exception("Error processing job")
        raise

    finally:
        # 後片付け
        for f in [locals().get(x) for x in ("local_audio", "fixed_audio", "template_path", "local_docx")]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
