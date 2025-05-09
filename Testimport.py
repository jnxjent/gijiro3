import os
from dotenv import load_dotenv

# .env の読み込み
load_dotenv()

# 環境変数を取得
ffmpeg_path = os.getenv("FFMPEG_PATH")
ffprobe_path = os.getenv("FFPROBE_PATH")

print("FFMPEG_PATH:", ffmpeg_path)
print("FFPROBE_PATH:", ffprobe_path)
