import logging

# ─── モジュール読み込み時のログ ─────────────────────────
logger = logging.getLogger("ProcessAudioFunction")
logger.setLevel(logging.INFO)
logger.info("▶▶ Module import start")

import os
import json
import base64
import tempfile
import subprocess
import uuid
from pathlib import Path

from pydub import AudioSegment
import azure.functions as func

from storage import download_blob, upload_to_blob
from kowake import transcribe_and_correct
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document

# ─── ffmpeg / ffprobe 検出ロジック（環境変数のみ） ──────────
ffmpeg_path = os.getenv("FFMPEG_BINARY", "")
ffprobe_path = os.getenv("FFPROBE_BINARY", "")

if not (ffmpeg_path and ffprobe_path and os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path)):
    logger.error("FFMPEG/FFPROBE binary not found. Check FFMPEG_BINARY and FFPROBE_BINARY env vars.")
    raise RuntimeError("FFMPEG/FFPROBE binary not found. Set env vars or include binaries.")

# PATH にディレクトリを追加（オプション）
bin_dir = str(Path(ffmpeg_path).parent)
os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

# pydub 用の設定
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe   = ffprobe_path

# ffmpeg / ffprobe パス検出結果をログ
logger.info(f"▶▶ Using FFMPEG_BINARY  : {ffmpeg_path}")
logger.info(f"▶▶ Using FFPROBE_BINARY : {ffprobe_path}")
logger.info("▶▶ Module import success")

# ─── 一時ディレクトリ準備 ─────────────────────────────────
TMP_DIR = tempfile.gettempdir()

async def main(msg: func.QueueMessage) -> None:
    # ─── 関数起動時のログ ───────────────────────────────────
    logger.info("▶▶ Function invoked")

    # ─── 生のメッセージをまずログ ───────────────────────────────
    raw = msg.get_body().decode("utf-8", errors="replace")
    logger.info("▶▶ RAW payload: %s", raw)

    try:
        # ─── JSON／Base64 自動判定デコード ─────────────────────────
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            decoded = base64.b64decode(raw).decode("utf-8")
            body = json.loads(decoded)

        job_id              = body["job_id"]
        blob_url            = body["blob_url"]
        template_blob_url   = body["template_blob_url"]
        logger.info(f"Received job {job_id}, blob: {blob_url}, template: {template_blob_url}")

        # 1. 音声を /tmp にダウンロード
        local_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")
        logger.info(f"▶▶ STEP1-1: Downloading audio from {blob_url}")
        download_blob(blob_url, local_audio)
        logger.info(f"▶▶ STEP1-2: Audio downloaded to {local_audio}")

        # 2. Fast-Start
        fixed_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}_fixed.mp4")
        subprocess.run([
            ffmpeg_path,
            "-y",
            "-i", local_audio,
            "-c", "copy",
            "-movflags", "+faststart",
            fixed_audio,
        ], check=True, timeout=60)
        logger.info(f"▶▶ STEP2: Faststart applied: {fixed_audio}")

        # 3. 文字起こし
        logger.info("▶▶ STEP3-1: Starting transcription")
        transcript = await transcribe_and_correct(fixed_audio)
        logger.info("▶▶ STEP3-2: Transcription completed")

        # 4. テンプレート DL
        template_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}_template.docx")
        logger.info(f"▶▶ STEP4-1: Downloading template from {template_blob_url}")
        download_blob(template_blob_url, template_path)
        logger.info(f"▶▶ STEP4-2: Template downloaded to {template_path}")

        # 5. 情報抽出 → Word
        logger.info("▶▶ STEP5-1: Starting document processing")
        meeting_info = await extract_meeting_info_and_speakers(transcript, template_path)
        local_docx = os.path.join(TMP_DIR, f"{job_id}.docx")
        blob_docx  = f"processed/{job_id}.docx"
        process_document(template_path, local_docx, meeting_info)
        logger.info("▶▶ STEP5-2: Document processed")

        with open(local_docx, "rb") as fp:
            upload_to_blob(blob_docx, fp, add_audio_prefix=False)
        logger.info(f"Job {job_id} completed, saved to {blob_docx}")

    except Exception:
        logger.exception("Error processing job")
        raise

    finally:
        # 後片付け
        for var in ("local_audio", "fixed_audio", "template_path", "local_docx"):
            path = locals().get(var)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
