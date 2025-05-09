from flask_sqlalchemy import SQLAlchemy

# Flaskアプリで使用するDBインスタンス
db = SQLAlchemy()

# キーワード登録用のモデル
class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reading = db.Column(db.String(100), nullable=False)           # 読み方
    keyword = db.Column(db.String(100), nullable=False)           # 正しい表記
    wrong_examples = db.Column(db.Text, nullable=True)            # 誤表記（カンマ区切り）

    def __repr__(self):
        return f"<Keyword {self.reading} -> {self.keyword}>"
