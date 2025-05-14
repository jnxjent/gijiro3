import os
import subprocess
from pydub import AudioSegment
from pydub.utils import which

# 環境変数の設定
ffmpeg_path = "C:/Users/021213/ffmpeg/bin/ffmpeg.exe"
ffprobe_path = "C:/Users/021213/ffmpeg/bin/ffprobe.exe"

# `pydub` の `converter` と `ffprobe` の設定
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

# `PATH` 環境変数に ffmpeg のディレクトリを追加（必要な場合）
ffmpeg_dir = os.path.dirname(ffmpeg_path)
if ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + ";" + os.environ["PATH"]

# 確認用デバッグ出力
print("[DEBUG] Checking FFmpeg and FFprobe paths detected by pydub:")
print("pydub.utils.which('ffmpeg'):", which("ffmpeg"))
print("pydub.utils.which('ffprobe'):", which("ffprobe"))
print("AudioSegment.converter:", AudioSegment.converter)
print("AudioSegment.ffprobe:", AudioSegment.ffprobe)

# `subprocess` で `ffmpeg` を実行して確認
print("\n[DEBUG] Running ffmpeg command...")
try:
    result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
    print("FFmpeg Output:\n", result.stdout)
except FileNotFoundError:
    print("[ERROR] FFmpeg not found in the system path!")

# `subprocess` で `ffprobe` を実行して確認
print("\n[DEBUG] Running ffprobe command...")
try:
    result = subprocess.run([ffprobe_path, "-version"], capture_output=True, text=True)
    print("FFprobe Output:\n", result.stdout)
except FileNotFoundError:
    print("[ERROR] FFprobe not found in the system path!")
