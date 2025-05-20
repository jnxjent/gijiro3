#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py – Flask エントリポイント
-------------------------------
・ffmpeg / ffprobe の実行ファイナリを OS 別に設定
・pydub が参照する環境変数を上書き
・CORS, ルーティング, waitress 起動
"""

import os
import platform
from pydub import AudioSegment
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS

# 環境変数を .env からロード
load_dotenv()

# ffmpeg / ffprobe 実行ファイルパス設定
if platform.system() == "Windows":
    FFMPEG_BIN = os.getenv("FFMPEG_PATH_WIN", "ffmpeg")
    FFPROBE_BIN = os.getenv("FFPROBE_PATH_WIN", "ffprobe")
else:
    FFMPEG_BIN = os.getenv("FFMPEG_PATH_UNIX", "/home/site/ffmpeg-bin/bin/ffmpeg")
    FFPROBE_BIN = os.getenv("FFPROBE_PATH_UNIX", "/home/site/ffmpeg-bin/bin/ffprobe")

# pydub に実ファイルを認識させる
AudioSegment.converter = FFMPEG_BIN
AudioSegment.ffprobe = FFPROBE_BIN
os.environ["FFMPEG_BINARY"] = FFMPEG_BIN
os.environ["FFPROBE_BINARY"] = FFPROBE_BIN

# Flask アプリの生成（template_folder を明示）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
app = Flask(__name__, template_folder=TEMPLATE_DIR)
CORS(app)

# --- ルーティング登録 ---
try:
    from routes import setup_routes
    print("✔ routes.py を読み込みます")
    setup_routes(app)
    print("✔ setup_routes 実行完了")
except Exception as e:
    print(f"[WARNING] routes.py の読み込みに失敗しました: {e}")

# --- Flask サーバー起動 ---
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 8000))
    print(f"[INFO] Starting server on http://127.0.0.1:{port}")
    serve(app, host="0.0.0.0", port=port)
