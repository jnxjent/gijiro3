import os
from pathlib import Path
from table_writer import table_writer
from minutes_writer import write_minutes_section

def process_document(word_file_path: str, output_file_path: str, extracted_info: dict):
    """
    統合関数: テーブルの更新と議事録の書き込みを処理する

    :param word_file_path: 読み込む Word テンプレートのファイルパス
    :param output_file_path: 出力先（更新後の Word ファイルのパス）
    :param extracted_info: 生成AIが抽出した辞書データ {label: value, replaced_transcription: "..."}
    """
    print(f"[INFO] Wordテンプレート: {word_file_path}")
    print(f"[INFO] 出力ファイル: {output_file_path}")
    print(f"[INFO] 抽出情報: {len(extracted_info)} 個")

    Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

    if not extracted_info:
        raise ValueError("extracted_info が空です")

    try:
        # ✅ テーブル更新
        table_writer(word_file_path, output_file_path, extracted_info)
    except Exception as e:
        print(f"[ERROR] テーブル更新中にエラー: {e}")
        raise

    replaced_transcription = extracted_info.get("replaced_transcription", "")
    if not replaced_transcription:
        print("[WARNING] replaced_transcription が空のため、議事録本文は未挿入の可能性があります")

    try:
        # ✅ 議事録本文の挿入
        write_minutes_section(output_file_path, output_file_path, replaced_transcription)
    except Exception as e:
        print(f"[ERROR] 議事録本文挿入中にエラー: {e}")
        raise

    # ✅ ファイルが正常に出力されたかチェック
    if not os.path.exists(output_file_path):
        raise RuntimeError(f"[ERROR] Wordファイルが生成されていません: {output_file_path}")

    file_size = os.path.getsize(output_file_path)
    if file_size < 1000:
        raise RuntimeError(f"[ERROR] Wordファイルのサイズが異常です（{file_size}バイト）: {output_file_path}")

    print(f"[INFO] Word 議事録生成完了: {output_file_path}")
