from pathlib import Path
from storage import upload_to_blob

# --- アップロードしたいローカルファイル ---
local_path = Path(r"C:\Users\021213\OneDrive - 株式会社ミダック\ドキュメント\AI研究会\議事録アプリ関連\音源サンプル\BLOB_サンプル会議音声 - コピー.mp4")

# Blob 上で付けたいファイル名（拡張子含めてそのまま）
blob_name = local_path.name          # "BLOB_サンプル会議音声 - コピー.mp4"
#  ↑ 既定で add_audio_prefix=True なので最終的には mom/audio/以下に置かれる

# --- アップロード ---
with local_path.open("rb") as fp:
    blob_url = upload_to_blob(blob_name, fp, add_audio_prefix=True)

print("アップロード完了:", blob_url)
