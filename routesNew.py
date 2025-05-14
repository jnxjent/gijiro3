--- routes.py
@@
-    @app.route('/results/<job_id>', methods=['GET'])
-    def result_page(job_id):
-        return render_template("results.html", job_id=job_id)
+    @app.route('/results/<job_id>', methods=['GET'])
+    def result_page(job_id):
+        # テンプレート名を実ファイル名 result.html に合わせる
+        return render_template("result.html", job_id=job_id)
