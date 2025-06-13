from azure.storage.queue import QueueClient

conn_str = "DefaultEndpointsProtocol=https;AccountName=midac19stoyhggrda5qr5ae;AccountKey=djycnwAjqjlj70f1PVgBStfJ8+ZfW04lcE5Laixln7IbhOrM9J0H+KJEjpVbt7NbdgXuI3Fzp3mD+AStMbUyhw==;EndpointSuffix=core.windows.net"
queue_name = "audio-processing"

queue = QueueClient.from_connection_string(conn_str, queue_name)
# メッセージを最大 5 件受信（visibility_timeout=5 秒）
messages = queue.receive_messages(max_messages=5, visibility_timeout=5)
for msg in messages:
    print(msg.id, msg.content)  # msg.content が JSON 文字列になっているはず
