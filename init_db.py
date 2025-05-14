import os
from flask import Flask
from models import db

# Flaskアプリの作成
app = Flask(__name__)

# データベースURIの設定（例：ローカルSQLite）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keywords.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# DB初期化
db.init_app(app)

with app.app_context():
    db.create_all()
    print("✅ データベースの初期化が完了しました。")
