    import time
    from flask import send_file

    @app.route('/api/process/<job_id>/wait', methods=['GET'])
    def api_wait_for_result(job_id):
        """
        結果ファイルが生成されるまで待機し、あれば返す。なければ504。
        """
        max_wait_sec = 600  # 最大10分
        interval_sec = 5
        result_blob = f"results/{job_id}.docx"
        blob_client = BlobClient.from_connection_string(
            os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            os.getenv("AZURE_STORAGE_CONTAINER_NAME"),
            result_blob
        )

        elapsed = 0
        while elapsed < max_wait_sec:
            if blob_client.exists():
                # 一時ファイルに保存して返却（またはURLを返す）
                local_path = Path("downloads") / f"{job_id}.docx"
                with open(local_path, "wb") as f:
                    download_stream = blob_client.download_blob()
                    f.write(download_stream.readall())
                return send_file(local_path, as_attachment=True)

            time.sleep(interval_sec)
            elapsed += interval_sec

        return jsonify({"error": "処理が完了しませんでした"}), 504
