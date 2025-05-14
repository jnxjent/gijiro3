import os
from pydub import AudioSegment

ffmpeg_path = r"C:\Users\021213\ffmpeg\bin\ffmpeg.exe"
ffprobe_path = r"C:\Users\021213\ffmpeg\bin\ffprobe.exe"

# 環境変数をセット
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path

# `pydub` に明示的に設定
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

print("AudioSegment.converter:", AudioSegment.converter)
print("AudioSegment.ffprobe:", AudioSegment.ffprobe)
