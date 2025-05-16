#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py  –  Flask エントリポイント
--------------------------------
・ffmpeg / ffprobe の実行ファイナリを OS 別に設定
・pydub が参照する環境変数を上書き
・CORS, ルーティング, waitress 起動
"""

import os
import platform
from pydub import AudioSegment
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

# 環境変数を .env からロード
load_dotenv()

# ffmpeg / ffprobe 実行ファイルパス設定（例: Linux と Windows で切り分け）
if platform.system() == "Windows":
    FFMPEG_BIN = os.getenv("FFMPEG_PATH_WIN", "ffmpeg")
    FFPROBE_BIN = os.getenv("FFPROBE_PATH_WIN", "ffprobe")
else:
    FFMPEG_BIN = os.getenv("FFMPEG_PATH_UNIX", "/home/site/ffmpeg-bin/bin/ffmpeg")
    FFPROBE_BIN = os.getenv("FFPROBE_PATH_UNIX", "/home/site/ffmpeg-bin/bin/ffprobe")

# pydub に実ファイルを認識させる
os.environ["FFMPEG_BINARY"] = FFMPEG_BIN
os.environ["FFPROBE_BINARY"] = FFPROBE_BIN

# Flask アプリの生成
app = Flask(__name__)
# 必要に応じて CORS の設定をカスタマイズ
CORS(app)

# --- health check endpoint ---
@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="ok"), 200

# --- ここから他のルートや Blueprint を登録 ---
# from your_module import blueprint_or_route_function
# app.register_blueprint(blueprint_or_route_function)

# 例: POST で audio+WORD ファイルを受け取るルート
# @app.route("/api/process-audio", methods=["POST"])
# def process_audio():
#     # ファイル受け取り→処理→レスポンス
#     return jsonify(result="success"), 200

# ---------------------------------------------------

if __name__ == "__main__":
    # 本番用には waitress で起動
    from waitress import serve
    port = int(os.environ.get("PORT", 8000))
    serve(app, host="0.0.0.0", port=port)
