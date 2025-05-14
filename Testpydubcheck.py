from pydub.utils import which

ffmpeg_exe = which("ffmpeg")
ffprobe_exe = which("ffprobe")

print("ffmpeg path detected by pydub:", ffmpeg_exe)
print("ffprobe path detected by pydub:", ffprobe_exe)
