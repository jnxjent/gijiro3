import os
from pydub import AudioSegment
from pydub.utils import which

# FFMPEGとFFPROBEのパスを手動で設定
os.environ["FFMPEG_BINARY"] = "C:/Users/021213/ffmpeg/bin/ffmpeg.exe"
os.environ["FFPROBE_BINARY"] = "C:/Users/021213/ffmpeg/bin/ffprobe.exe"

# pydubにパスを設定
AudioSegment.converter = os.environ["FFMPEG_BINARY"]
AudioSegment.ffprobe = os.environ["FFPROBE_BINARY"]

# 設定確認
print("[DEBUG] FFmpeg & FFprobe path settings updated.")
print("pydub.utils.which('ffmpeg'):", which("ffmpeg"))
print("pydub.utils.which('ffprobe'):", which("ffprobe"))
print("AudioSegment.converter:", AudioSegment.converter)
print("AudioSegment.ffprobe:", AudioSegment.ffprobe)
