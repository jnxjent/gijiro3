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
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
from routes import setup_routes
from kowake import load_keywords_from_file

# .env 読み込み ------------------------------------------------------------
load_dotenv()

# ─────────────── ffmpeg / ffprobe バイナリ設定 ───────────────
BASE_DIR = os.path.dirname(__file__)

# フォルダ構成を「ffmpeg/bin/<os>/ffmpeg(.exe)」に合わせる
BIN_ROOT    = os.path.join(BASE_DIR, "ffmpeg", "bin")
LINUX_DIR   = os.path.join(BIN_ROOT, "linux")
WINDOWS_DIR = os.path.join(BIN_ROOT, "win")

if platform.system() == "Windows":
    ffmpeg_path  = os.path.join(WINDOWS_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(WINDOWS_DIR, "ffprobe.exe")
    os.environ["PATH"] = f"{WINDOWS_DIR};" + os.environ.get("PATH", "")
else:
    ffmpeg_path  = os.path.join(LINUX_DIR, "ffmpeg")
    ffprobe_path = os.path.join(LINUX_DIR, "ffprobe")
    os.environ["PATH"] = f"{LINUX_DIR}:" + os.environ.get("PATH", "")

os.environ["FFMPEG_BINARY"]  = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path
AudioSegment.converter       = ffmpeg_path
AudioSegment.ffprobe         = ffprobe_path

print(f"Using FFMPEG_BINARY : {os.environ['FFMPEG_BINARY']}")
print(f"Using FFPROBE_BINARY: {os.environ['FFPROBE_BINARY']}")
print(f"PATH begins with    : {os.environ['PATH'].split(os.pathsep)[0]}")
# ─────────────────────────────────────────────────────────────

def create_app():
    """Flask アプリ生成 & ルート登録"""
    app = Flask(__name__)
    CORS(app)                       # CORS（プリフライト含む）許可
    app.url_map.strict_slashes = False

    # --- 本来のルーティング登録 ---
    setup_routes(app)               # routes.py に定義された /health, /process など
    load_keywords_from_file()       # kowake.py のキーワード辞書ロード

    return app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    from waitress import serve      # 本番は waitress で起動
    serve(create_app(), host="0.0.0.0", port=port, threads=4)
