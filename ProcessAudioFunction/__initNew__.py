# __init__.py – 非同期版（minutes_writer 前提で整形済み議事を抽出）

import os
import json
import tempfile
import logging
import platform
import subprocess                # ← 追加: ffmpeg を呼び出すため
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

        # ─── 新規追加: Blob を一度ローカルにダウンロード ───
        tmp_mp4 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        download_blob(blob_url, tmp_mp4)
        logger.info(f"Downloaded blob to {tmp_mp4}")

        # ─── ① Fast-Start で moov atom を先頭に移動 ───
        fixed_mp4 = tmp_mp4.replace(".mp4", "_fixed.mp4")
        subprocess.run([
            AudioSegment.converter, "-y",
            "-i", tmp_mp4,
            "-c", "copy",
            "-movflags", "+faststart",
            fixed_mp4
        ], check=True)
        logger.info(f"Fast-start applied, output {fixed_mp4}")

        # ─── ② フォールバック：WAV に変換しておく（必要ならこちらを使う） ───
        # wav_file = tmp_mp4.replace(".mp4", ".wav")
        # subprocess.run([
        #     AudioSegment.converter, "-y",
        #     "-i", fixed_mp4,
        #     "-acodec", "pcm_s16le",
        #     "-ar", "16000",
        #     wav_file
        # ], check=True)
        # audio_input = wav_file

        # 通常は MP4 ファイルをそのまま渡します
        audio_input = fixed_mp4

        # ✅ 1. 音声 → 整形済みテキスト生成（Deepgram + OpenAI）
        #    ここでローカルファイルを読み込むよう、transcribe_and_correct を修正してください
        transcript = await transcribe_and_correct(audio_input)

        # 後片付け
        os.remove(tmp_mp4)
        os.remove(fixed_mp4)
        # if os.path.exists(wav_file): os.remove(wav_file)

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
        with open(output_docx, "rb") as fstream:
            upload_to_blob(output_docx, fstream, add_audio_prefix=False)

        logger.info(f"Job {job_id} completed, result saved to {output_docx}")

    except Exception as e:
        logger.error(f"Error processing job: {e}")
        raise
