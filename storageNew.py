# ...（省略されていない import はそのまま）...

def _normalize_blob_name(blob_name: str, *, force_audio_prefix: bool = False) -> str:
    if force_audio_prefix:
        if blob_name.startswith("audio/"):
            return blob_name
        if blob_name.startswith("word/") or blob_name.startswith("results/") or blob_name.startswith("settings/") or blob_name.startswith("processed/"):
            return blob_name  # ⛔ audio/word/... にならないよう除外
        return f"audio/{blob_name}"
    return blob_name  # ✅ False の場合はそのまま使用

# ...（他の関数定義も同様、変更不要）...
