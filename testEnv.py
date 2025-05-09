import os
from dotenv import load_dotenv

# .envファイルの内容を読み込む
load_dotenv()

# 環境変数を取得
secret_key = os.getenv('SECRET_KEY')

# 環境変数の値を表示
print(f'SECRET_KEY: {secret_key}')
