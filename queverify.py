# que_verify.py
from azure.storage.queue import QueueClient
import os

# Web App / Function に設定されているのと同じ接続文字列を直接代入するか、
# 環境変数 AZ_CONN に設定しておく
conn_str = os.getenv("AZ_CONN") or (
    "DefaultEndpointsProtocol=https;"
    "AccountName=midac19stoyhggrda5qr5ae;"
    "AccountKey=djycnwAjqjlj70f1PVgBStfJ8+ZfW04lcE5Laixln7IbhOrM9J0H+KJEjpVbt7NbdgXuI3Fzp3mD+AStMbUyhw==;"
    "EndpointSuffix=core.windows.net"
)
queue_name = "audio-processing"

q = QueueClient.from_connection_string(conn_str, queue_name)

# 1) まず peek
print("── peek──")
for msg in q.peek_messages(max_messages=5):
    print(msg.content)

# 2) 手動で送ってみる
print("── send──")
res = q.send_message('{"job_id":"script_test","blob_url":"","template_blob_url":""}')
print("sent id:", res.id)

# 3) 再度 peek
print("── peek after send──")
for msg in q.peek_messages(max_messages=5):
    print(msg.content)
