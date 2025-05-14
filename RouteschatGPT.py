import os
import logging
import json
import asyncio
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from storage import upload_to_blob, download_blob
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document
from pathlib import Path
from datetime import datetime
from models import db, Keyword  # ✅ Keywordモデル
from kowake import transcribe_and_correct, replace_with_custom_keywords

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if app.secret_key is None:
    raise ValueError("SECRET_KEY環境変数が設定されていません。")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keywords.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ✅ キーワード読み込み関数
def get_custom_keyword_entries():
    return [(kw.reading, kw.word) for kw in Keyword.query.all()]

@app.route('/', methods=['GET', 'POST'])
async def upload():
    if request.method == 'POST':
        try:
            audio_file = request.files.get('audio_file')
            word_file = request.files.get('word_file')

            if not audio_file or not word_file:
                return render_template("error.html", message="音声ファイルと Word ファイルを両方アップロードしてください。"), 400

            audio_blob_name = f"audio/{audio_file.filename}"
            word_blob_name = f"word/{word_file.filename}"

            audio_url = upload_to_blob(audio_blob_name, audio_file.stream)
            word_url = upload_to_blob(word_blob_name, word_file.stream)

            if not audio_url or not word_url:
                return render_template("error.html", message="Blob URL generation failed"), 500

            downloads_dir = Path("./downloads"); downloads_dir.mkdir(exist_ok=True)
            uploads_dir = Path("./uploads"); uploads_dir.mkdir(exist_ok=True)

            audio_local_path = downloads_dir / audio_file.filename
            word_local_path = downloads_dir / word_file.filename

            download_blob(audio_blob_name, str(audio_local_path))
            download_blob(word_blob_name, str(word_local_path))

            timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
            output_filename = f"updated_meeting_notes - {timestamp}.docx"
            output_file_local = uploads_dir / output_filename

            keyword_entries = get_custom_keyword_entries()

            transcription_raw = await transcribe_and_correct(str(audio_local_path))
            transcription = replace_with_custom_keywords(transcription_raw, keyword_entries)
            extracted_info = await extract_meeting_info_and_speakers(transcription, str(word_local_path))

            if not extracted_info:
                return render_template("error.html", message="議事録の情報抽出に失敗しました"), 500

            try:
                process_document(str(word_local_path), str(output_file_local), extracted_info)
            except Exception as e:
                return render_template("error.html", message=f"Wordファイルの更新に失敗しました: {e}"), 500

            try:
                with open(output_file_local, "rb") as f:
                    final_doc_blob_path = f"processed/{output_filename}"
                    updated_word_url = upload_to_blob(final_doc_blob_path, f)

                if not updated_word_url:
                    return render_template("error.html", message="処理後の Word ファイルのアップロードに失敗しました"), 500

            except Exception as e:
                return render_template("error.html", message=f"処理後の Word ファイルのアップロードに失敗: {e}"), 500

            return render_template("result.html",
                                   message="処理成功！",
                                   output_file_path=str(output_file_local).replace("\\", "/"),
                                   uploaded_audio_url=audio_url,
                                   uploaded_word_url=word_url,
                                   updated_word_url=updated_word_url)
        except Exception as e:
            return render_template("error.html", message=f"Error during processing: {e}"), 500

    return render_template("index.html")

# ✅ キーワード一覧ページ
@app.route('/keywords', methods=['GET'])
def list_keywords():
    keywords = Keyword.query.all()
    return render_template("keywords.html", keywords=keywords)

# ✅ キーワード追加処理
@app.route('/keywords/add', methods=['POST'])
def add_keyword():
    reading = request.form.get('reading')
    word = request.form.get('word')
    if reading and word:
        new_kw = Keyword(reading=reading, word=word)
        db.session.add(new_kw)
        db.session.commit()
        flash("キーワードを追加しました。")
    else:
        flash("読み方とキーワードの両方を入力してください。")
    return redirect(url_for('list_keywords'))

# ✅ キーワード編集処理
@app.route('/keywords/edit/<int:id>', methods=['POST'])
def edit_keyword(id):
    keyword = Keyword.query.get_or_404(id)
    keyword.reading = request.form.get('reading')
    keyword.word = request.form.get('word')
    db.session.commit()
    flash("キーワードを更新しました。")
    return redirect(url_for('list_keywords'))

# ✅ キーワード削除処理
@app.route('/keywords/delete/<int:id>', methods=['POST'])
def delete_keyword(id):
    keyword = Keyword.query.get_or_404(id)
    db.session.delete(keyword)
    db.session.commit()
    flash("キーワードを削除しました。")
    return redirect(url_for('list_keywords'))

@app.route('/api/auth/callback/azure-ad', methods=['GET', 'POST'])
def azure_ad_callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            return jsonify({"error": error}), 400

        if not code:
            return jsonify({"error": "認証コードがありません"}), 400

        return jsonify({
            "message": "Azure AD 認証成功！",
            "code": code,
            "state": state
        })
    except Exception as e:
        return jsonify({"error": f"エラー発生: {e}"}), 500
