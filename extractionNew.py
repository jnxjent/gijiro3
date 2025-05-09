import os
import openai
import re
from dotenv import load_dotenv
from docx import Document

load_dotenv()

TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
DEPLOYMENT_ID = os.getenv("DEPLOYMENT_ID")

async def extract_meeting_info_and_speakers(transcribed_text: str, word_template_path: str = None) -> dict:
    """
    1. 生成済み文字起こし（整形済み）を元に情報抽出
    2. WORDテンプレートからラベルを取得
    3. 話者推定と置換後の全文作成
    4. 各ラベルに対応する情報をAIから抽出
    """

    # -------------------------------------------
    # (A) 生成済みの全文文字起こし
    # -------------------------------------------
    full_transcription = transcribed_text or ""

    # -------------------------------------------
    # (B) WORDテンプレートからラベルを取得
    # -------------------------------------------
    table_labels = []
    if word_template_path:
        doc = Document(word_template_path)
        for table in doc.tables:
            for row in table.rows:
                if len(row.cells) >= 1:
                    label = row.cells[0].text.strip().rstrip("：:")
                    if label:
                        table_labels.append(label)

    print(f"[DEBUG] 抽出されたラベル一覧: {table_labels}")

    # `extracted_info` の初期化
    extracted_info = {label: "" for label in table_labels}
    extracted_info["推定話者"] = {}
    extracted_info["full_transcription"] = full_transcription

    # -------------------------------------------
    # (C) 話者推定と全文置換
    # -------------------------------------------
    try:
        prompt_speakers = (
            "以下のテキストで '[Speaker 0]' や '[Speaker 1]' のような表記を、"
            "実際の話者名や役職に推定変換してください。\n"
            "敬称『さん』は付けず、名前だけにしてください。\n"
            "不明な場合は '[Speaker 0]→不明0' としてください。\n\n"
            f"=== 議事録全文 ===\n{full_transcription}\n\n"
            "【出力形式】:\n"
            "- Speaker 0 -> 田中\n"
            "- Speaker 1 -> 山田\n"
        )
        response_speakers = openai.ChatCompletion.create(
            engine=DEPLOYMENT_ID,
            messages=[
                {"role": "system", "content": "あなたは文字起こしを整理し、話者名を推定するアシスタントです。"},
                {"role": "user", "content": prompt_speakers}
            ],
            max_tokens=4000,
            temperature=0,
        )

        content_speakers = (
            response_speakers.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not content_speakers:
            raise ValueError("話者推定APIのレスポンスが空です")

        speaker_map = {}
        for line in content_speakers.splitlines():
            match = re.match(r"^-?\s*Speaker\s*(\d+)\s*->\s*(.+)$", line)
            if match:
                speaker_tag = f"Speaker {match.group(1).strip()}"
                speaker_name = match.group(2).strip()
                speaker_map[speaker_tag] = speaker_name

        extracted_info["推定話者"] = speaker_map
        print(f"[DEBUG] 推定された話者マッピング: {speaker_map}")

        # 話者を議事録内で置換
        replaced_transcription = full_transcription
        for speaker_tag, speaker_name in speaker_map.items():
            replaced_transcription = re.sub(
                rf"\[?\b{re.escape(speaker_tag)}\b\]?", f"[{speaker_name}]", replaced_transcription
            )

        extracted_info["replaced_transcription"] = replaced_transcription
        print("[LOG] 話者変換後の議事録:")
        print(replaced_transcription)
    except Exception as e:
        extracted_info["推定話者"] = {}
        print(f"[ERROR] 話者推定に失敗しました: {e}")

    # -------------------------------------------
    # (D) ラベルごとに情報を抽出 (議題は番号付きリスト化)
    # -------------------------------------------
    if table_labels:
        for label in table_labels:
            try:
                prompt_info = (
                    f"以下の会議議事録全文から、'{label}' に該当する情報を抜き出してください。\n"
                    "内容を簡潔にまとめ、日本語で回答してください。\n"
                    "※議題の場合は、番号付きリストにしてください（1. 〇〇\\n2. ▲▲ の形式）。\n\n"
                    f"=== 議事録全文 ===\n{replaced_transcription}\n\n"
                    f"【出力形式】:\n- {label}: <抽出情報>"
                )
                response_info = openai.ChatCompletion.create(
                    engine=DEPLOYMENT_ID,
                    messages=[
                        {"role": "system", "content": "あなたは会議の議事録を解析し、指定された情報を正確に抽出するアシスタントです。"},
                        {"role": "user", "content": prompt_info}
                    ],
                    max_tokens=4000,
                    temperature=0,
                )
                extracted_value = (
                    response_info.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )

                # 📌 **議題をリスト形式に修正**
                if label == "議題":
                    items = re.split(r"[、,]", extracted_value)
                    extracted_value = "\n".join([f"{i+1}. {item.strip()}" for i, item in enumerate(items)])

                extracted_info[label] = extracted_value

            except Exception as e:
                print(f"[ERROR] {label} の抽出中にエラーが発生しました: {e}")
                extracted_info[label] = "抽出エラー"

    print(f"[DEBUG] Final extracted_info content: {extracted_info}")
    return extracted_info