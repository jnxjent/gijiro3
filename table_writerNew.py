def clean_repeated_labels(label: str, value: str) -> str:
    """
    `value` の冒頭に `label` が繰り返されている場合、それを削除する。
    - 記号 `:`, `：`, `-`, `～`, `ー` も考慮
    - "- label:" の形式も削除
    - ✅ 「1. - 議題:」を含んでいたら、その部分のみを削除
    """
    label = normalize_text(label)  # ラベルを正規化
    value = unicodedata.normalize("NFKC", value).strip()  # 値も正規化

    # `- label:` の形式や `label:` の繰り返しを削除
    pattern = rf"^[-\s]*{re.escape(label)}[\s:：\-～ー]*"
    cleaned_value = re.sub(pattern, '', value).strip()

    # ✅ 「1. - 議題:」を完全一致で削除
    cleaned_value = re.sub(r"1\. - 議題[:：]?", "", cleaned_value).strip()

    return cleaned_value
