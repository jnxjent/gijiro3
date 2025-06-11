import os
import json
import tempfile
import logging
import platform
import subprocess
import uuid

from pydub import AudioSegment
import azure.functions as func

from storage import download_blob, upload_to_blob
from kowake import transcribe_and_correct
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document

# ─── ffmpeg / ffprobe のパス設定 ───────────────────────────
ffmpeg_dir = r"C:\\Users\\021213\\ffmpeg\\bin\\win"
if platform.system() == "Windows":
    os.environ["PATH"] = ffmpeg_dir + ";" + os.environ.get("PATH", "")
    AudioSegment.converter = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")
    os.environ["FFMPEG_BINARY"] = AudioSegment.converter
    os.environ["FFPROBE_BINARY"] = AudioSegment.ffprobe
    print(f"[INIT] FFMPEG_BINARY  : {AudioSegment.converter}")
    print(f"[INIT] FFPROBE_BINARY : {AudioSegment.ffprobe}")

# ─── ロガー設定 ─────────────────────────────────────────────
logger = logging.getLogger("ProcessAudioFunction")
logger.setLevel(logging.INFO)

# ─── 一時ディレクトリ ───────────────────────────────────────
TMP_DIR = tempfile.gettempdir()  # Linux: /tmp, Windows: %TEMP%


async def main(msg: func.QueueMessage) -> None:
    try:
        body = json.loads(msg.get_body().decode())
        job_id = body["job_id"]
        blob_url = body["blob_url"]
        template_blob_url = body["template_blob_url"]
        logger.info(f"Received job {job_id}, blob: {blob_url}, template: {template_blob_url}")

        # ─── 1. 音声ファイルを /tmp へダウンロード ───
        local_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")
        download_blob(blob_url, local_audio)
        logger.info(f"Downloaded audio → {local_audio}")

        # ─── 2. Fast-Start (moov atom 先頭移動) ───
        fixed_audio = os.path.join(TMP_DIR, f"{uuid.uuid4()}_fixed.mp4")
        subprocess.run([
            AudioSegment.converter,
            "-y",
            "-i",
            local_audio,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            fixed_audio,
        ], check=True)
        logger.info(f"Fast-start output → {fixed_audio}")

        # ─── 3. 文字起こし＋整形 ───
        transcript = await transcribe_and_correct(fixed_audio)

        # ─── 4. Word テンプレートを /tmp に DL ───
        template_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}_template.docx")
        download_blob(template_blob_url, template_path)

        # ─── 5. 情報抽出 → Word 生成 ───
        meeting_info = await extract_meeting_info_and_speakers(
            transcribed_text=transcript,
            word_template_path=template_path,
        )

        local_docx = os.path.join(TMP_DIR, f"{job_id}.docx")
        blob_docx = f"processed/{job_id}.docx"
        process_document(template_path, local_docx, meeting_info)

        # ─── 6. Blob へアップロード ───
        with open(local_docx, "rb") as fp:
            upload_to_blob(blob_docx, fp, add_audio_prefix=False)
        logger.info(f"Job {job_id} completed, result saved to {blob_docx}")

    except Exception:
        logger.exception("Error processing job")
        raise
    finally:
        # ─── 後片付け ───
        for f in (locals().get("local_audio"), locals().get("fixed_audio"), locals().get("template_path"), locals().get("local_docx")):
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
