import asyncio
import sys
from kowake import transcribe_and_correct
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python processing.py <audio_file_path> <template_path> <output_file_path>")
        sys.exit(1)

    audio_file_path = sys.argv[1]
    template_path = sys.argv[2]
    output_file_path = sys.argv[3]

    try:
        # 1️⃣ 音声認識（transcribe）
        print("[STEP] 音声ファイルの文字起こし中...")
        replaced_text = asyncio.run(transcribe_and_correct(audio_file_path))

        # 2️⃣ 情報抽出（OpenAI）
        print("[STEP] 情報抽出と話者推定中...")
        extracted_info = extract_meeting_info_and_speakers(replaced_text)
        if not isinstance(extracted_info, dict):
            raise ValueError("extracted_info が辞書型ではありません")

        # 3️⃣ transcript を辞書に追加（docwriter 連携用）
        extracted_info["replaced_transcription"] = replaced_text
        print("[OK] 議事録情報＆話者推定が完了")

        # 4️⃣ Wordファイル出力
        print("[STEP] Wordファイルへの書き込み中...")
        process_document(template_path, output_file_path, extracted_info)

        print(f"[OK] Word出力完了: {output_file_path}")
        print("処理完了")

    except Exception as e:
        print(f"[ERROR] 処理中にエラーが発生しました: {e}")
        sys.exit(1)
