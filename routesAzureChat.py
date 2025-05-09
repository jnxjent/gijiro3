import os
import logging
import asyncio
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from storage import upload_to_blob, download_blob
from extraction import extract_meeting_info_and_speakers
from docwriter import process_document
from pathlib import Path
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import db, Keyword
from kowake import transcribe_and_correct, replace_with_custom_keywords

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if app.secret_key is None:
    raise ValueError("SECRET_KEY環境変数が設定されていません。")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keywords.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ロガーの設定
logger = logging.getLogger("routes")
logging.basicConfig(level=logging.INFO)

@app.route('/', methods=['GET', 'POST'])
async def upload():
    if request.method == 'POST':
        try:
            audio_file = request.files.get('audio_file')
            word_file = request.files.get('word_file')

            if not audio_file or not word_file:
                logger.error(f"Files missing. audio_file={audio_file}, word_file={word_file}")
                return render_template("error.html", message="音声ファイルと Word ファイルを両方アップロードしてください。"), 400

            audio_blob_name = f"audio/{audio_file.filename}"
            word_blob_name = f"word/{word_file.filename}"

            logger.info(f"Uploading audio: {audio_file.filename}")
            audio_url = upload_to_blob(audio_blob_name, audio_file.stream)

            logger.info(f"Uploading word: {word_file.filename}")
            word_url = upload_to_blob(word_blob_name, word_file.stream)

            if not audio_url or not word_url:
                logger.error("Blob URL generation failed.")
                return render_template("error.html", message="Blob URL generation failed"), 500

            downloads_dir = Path("./downloads")
            downloads_dir.mkdir(exist_ok=True)

            audio_local_path = downloads_dir / audio_file.filename
            word_local_path = downloads_dir / word_file.filename

            logger.info(f"Downloading audio file to {audio_local_path}")
            download_blob(audio_blob_name, str(audio_local_path))

            logger.info(f"Downloading word file to {word_local_path}")
            download_blob(word_blob_name, str(word_local_path))

            uploads_dir = Path("./uploads")
            uploads_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
            output_filename = f"updated_meeting_notes - {timestamp}.docx"
            output_file_local = uploads_dir / output_filename

            keyword_entries = get_custom_keyword_entries()

            transcription_raw = await transcribe_and_correct(str(audio_local_path))
            transcription = replace_with_custom_keywords(transcription_raw, keyword_entries)

            extracted_info = await extract_meeting_info_and_speakers(transcription, str(word_local_path))

            if not extracted_info:
                logger.error("[ERROR] extracted_info が空です")
                return render_template("error.html", message="議事録の情報抽出に失敗しました"), 500

            try:
                process_document(str(word_local_path), str(output_file_local), extracted_info)
                logger.info("[OK] Wordファイルへの転記が完了")
            except Exception as e:
                logger.error(f"[ERROR] process_document でエラー発生: {e}")
                return render_template("error.html", message=f"Wordファイルの更新に失敗しました: {e}"), 500

            try:
                with open(output_file_local, "rb") as f:
                    final_doc_blob_path = f"processed/{output_filename}"
                    updated_word_url = upload_to_blob(final_doc_blob_path, f)

                if not updated_word_url:
                    logger.error("[ERROR] 処理後の Word ファイルのアップロードに失敗")
                    return render_template("error.html", message="処理後の Word ファイルのアップロードに失敗しました"), 500

                logger.info(f"[OK] Updated Word file uploaded to Blob: {updated_word_url}")
            except Exception as e:
                logger.error(f"[ERROR] Word ファイルのアップロード中にエラー発生: {e}")
                return render_template("error.html", message=f"処理後の Word ファイルのアップロードに失敗: {e}"), 500

            return render_template("result.html",
                                   message="処理成功！",
                                   output_file_path=str(output_file_local).replace("\\", "/"),
                                   uploaded_audio_url=audio_url,
                                   uploaded_word_url=word_url,
                                   updated_word_url=updated_word_url)
        except Exception as e:
            logger.error(f"Error during processing: {e}")
            return render_template("error.html", message=f"Error during processing: {e}"), 500

    return render_template("index.html")

@app.route('/keywords', methods=['GET', 'POST'])
def manage_keywords():
    if request.method == 'POST':
        keyword = request.form.get('keyword')
        replacement = request.form.get('replacement')

        if keyword and replacement:
            new_keyword = Keyword(keyword=keyword, replacement=replacement)
            try:
                db.session.add(new_keyword)
                db.session.commit()
                flash("キーワードが追加されました！")
            except IntegrityError:
                db.session.rollback()
                flash("このキーワードは既に存在します。")
        else:
            flash("キーワードと置換語を両方入力してください。")

        return redirect(url_for('manage_keywords'))

    keywords = Keyword.query.all()
    return render_template('keywords.html', keywords=keywords)

# 🚀 Azure AD 認証コールバックエンドポイントを追加
@app.route('/api/auth/callback/azure-ad', methods=['GET', 'POST'])
def azure_ad_callback():
    """Azure AD の認証コールバックエンドポイント"""
    try:
        code = request.args.get("code")  # 認証コード
        state = request.args.get("state")  # 状態管理用のパラメータ
        error = request.args.get("error")  # 認証エラーがある場合

        if error:
            logger.error(f"認証エラー: {error}")
            return jsonify({"error": error}), 400

        if not code:
            logger.error("認証コードがありません")
            return jsonify({"error": "認証コードがありません"}), 400

        logger.info(f"Azure AD 認証成功！code={code}, state={state}")

        return jsonify({
            "message": "Azure AD 認証成功！",
            "code": code,
            "state": state
        })
    except Exception as e:
        logger.error(f"エラー発生: {e}")
        return jsonify({"error": f"エラー発生: {e}"}), 500

def get_custom_keyword_entries():
    """データベースからカスタムキーワードを取得"""
    keywords = Keyword.query.all()
    return {kw.keyword: kw.replacement for kw in keywords}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
