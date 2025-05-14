import requests

# ① Flask のエンドポイント
url = "http://127.0.0.1:8000/api/v1/upload_minutes"

# ② アップロードするファイルのパス
file_path = r"C:\Users\021213\Downloads\sample.docx"

# ③ SharePoint 情報
site_url    = "https://midaco365.sharepoint.com/sites/msteams_7d45a2_430935"
folder_path = "chattest"

# ④ ヘッダーに Authorization を追加（OBO優先の処理を client credentials fallback にさせる）
headers = {
    "X-Sp-Site": site_url,
    "X-Sp-Folder": folder_path,
    "Authorization": "Bearer dummy"
}

# ⑤ リクエスト準備
with open(file_path, "rb") as f:
    files = {"file": f}
    resp = requests.post(url, files=files, headers=headers)

# ⑥ 結果表示
print("Status Code:", resp.status_code)
print("Response Body:", resp.text)
