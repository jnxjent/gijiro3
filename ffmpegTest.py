from pydub import AudioSegment
import os

# 環境変数を取得
ffmpeg_path = os.getenv("FFMPEG_PATH")
ffprobe_path = os.getenv("FFPROBE_PATH")

# pydub に手動でパスを設定
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

# 設定を表示
print(f"Using FFmpeg: {AudioSegment.converter}")
print(f"Using FFprobe: {AudioSegment.ffprobe}")

# 簡単なオーディオ変換テスト (エラーが出ないか確認)
try:
    audio = AudioSegment.from_file("downloads/英語取材サンプル.m4a")
    print("音声ファイルの読み込み成功！")
except Exception as e:
    print(f"[ERROR] 音声ファイルの読み込み失敗: {e}")
