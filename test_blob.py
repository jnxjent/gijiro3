from azure.storage.blob import BlobServiceClient
import os, sys
from dotenv import load_dotenv
load_dotenv()

conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "mom")

svc = BlobServiceClient.from_connection_string(conn)
blobs = [b.name for b in svc.get_container_client(container).list_blobs(name_starts_with="audio/")]

print(f"{len(blobs)} blobs under audio/:")
for b in blobs:
    print("  ", b)
