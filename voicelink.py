import os  # ← 追加
audio_file = "downloads/会議音声サンプル_Full.mp4"

if os.path.exists(audio_file):
    print(f"[DEBUG] 音声ファイルが見つかりました: {audio_file}")
else:
    print(f"[ERROR] 音声ファイルが見つかりません: {audio_file}")
