from azure.storage.blob import BlobClient

def download_full_blob(blob_url: str, local_path: str):
    blob = BlobClient.from_blob_url(blob_url)
    # 1) ダウンロードストリームを取得
    stream = blob.download_blob()  

    # 2) 一括でバイナリを読み取り、ファイルに書き込む
    with open(local_path, "wb") as f:
        f.write(stream.readall())
