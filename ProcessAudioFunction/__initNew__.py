# __init__.py – 非同期版（minutes_writer 前提で整形済み議事を抽出）

import os
import json
import tempfile
import logging
import platform
from pydub import AudioSegment

# ─── ffmpeg / ffprobe をハードコードで設定 ───
ffmpeg_dir = r"C:\\Users\\021213\\ffmpeg\\bin\\win"
if platform.system() == "Windows":
    os.environ["PATH"] = ffmpeg_dir + ";" + os.environ.get("PATH", "")
    AudioSegment.converter = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")
    os.environ["FFMPEG_BINARY"] = AudioSegment.converter
    os.environ["FFPROBE_BINARY"] = AudioSegment.ffprobe
    print(f"[INIT] FFMPEG_BINARY  : {AudioSegment.converter}")
    print(f"[INIT] FFPROBE_BINARY : {AudioSegment.ffprobe}")

# ─── Azure Functions 関連 ───
import azure.functions as func
from storage import download_blob, upload_to_blob
from kowake import transcribe_and_correct
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document

logger = logging.getLogger("ProcessAudioFunction")
logger.setLevel(logging.INFO)

async def main(msg: func.QueueMessage) -> None:
    try:
        raw = msg.get_body().decode()
        body = json.loads(raw)
        job_id = body["job_id"]
        blob_url = body["blob_url"]
        template_blob_url = body["template_blob_url"]
        logger.info(f"Received job {job_id}, blob: {blob_url}, template: {template_blob_url}")

        # ✅ 1. 音声 → 整形済みテキスト生成（Deepgram + OpenAI）
        transcript = await transcribe_and_correct(blob_url)

        # ✅ 2. Wordテンプレート → 一時ファイルにDL
        tmp_template = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        template_path = download_blob(template_blob_url, tmp_template.name)

        # ✅ 3. 情報抽出（『■議事』付きテキストから AI が項目抽出）
        meeting_info = await extract_meeting_info_and_speakers(
            transcribed_text=transcript,
            word_template_path=template_path
        )

        # ✅ 4. Word作成（テンプレートに転記）
        output_docx = f"processed/{job_id}.docx"
        process_document(template_path, output_docx, meeting_info)

        # ✅ 5. 結果を Blob にアップロード
        #    バイナリモードで開いたファイルストリームを渡す
        with open(output_docx, "rb") as fstream:
            upload_to_blob(output_docx, fstream, add_audio_prefix=False)

        logger.info(f"Job {job_id} completed, result saved to {output_docx}")

    except Exception as e:
        logger.error(f"Error processing job: {e}")
        raise
