"""配色工具 Web 服务
启动: python server.py
访问: http://localhost:5000
"""

import os
import sys
import json
import io
import contextlib

from flask import Flask, render_template, request, jsonify, send_file

sys.path.insert(0, os.path.dirname(__file__))
import pipeline

app = Flask(__name__)

WORK_DIR = pipeline.WORK_DIR


def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_colors() -> dict:
    """返回默认配色 hex 值"""
    def h(rgb): return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return {"文字色": h(pipeline.DEFAULT_TEXT_COLOR),
            "tag色": h(pipeline.DEFAULT_TAG_COLOR),
            "tag底板色": h(pipeline.DEFAULT_TAG_BG_COLOR),
            "文字色_暗": h(pipeline.TEXT_COLOR_DARK),
            "tag色_暗": h(pipeline.TAG_COLOR_DARK),
            "tag底板色_暗": h(pipeline.TAG_BG_COLOR_DARK),
            "渐变上": h(pipeline.DEFAULT_GRADIENT_TOP),
            "渐变下": h(pipeline.DEFAULT_GRADIENT_BOTTOM)}


@app.route("/")
def index():
    return render_template("index.html", colors=get_colors())


@app.route("/generate", methods=["POST"])
def generate_preview():
    """颜色变化 → 快速生成缩略预览"""
    data = request.get_json()
    tc = hex_to_rgb(data["文字色"])
    tag = hex_to_rgb(data["tag色"])
    bg = hex_to_rgb(data["tag底板色"])
    tc_d = hex_to_rgb(data.get("文字色_暗", "#7ea6d2"))
    tag_d = hex_to_rgb(data.get("tag色_暗", "#afb0bf"))
    bg_d = hex_to_rgb(data.get("tag底板色_暗", "#546c94"))
    gt = hex_to_rgb(data.get("渐变上", "#e5f1ff"))
    gb = hex_to_rgb(data.get("渐变下", "#ffffff"))
    try:
        previews = pipeline.preview(tc, tag, bg, tc_d, tag_d, bg_d, gt, gb)
        return jsonify({"ok": True, "previews": previews})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/export", methods=["POST"])
def export_full():
    """导出高清原图（打包 ZIP 下载）"""
    data = request.get_json()
    tc = hex_to_rgb(data["文字色"])
    tag = hex_to_rgb(data["tag色"])
    bg = hex_to_rgb(data["tag底板色"])
    tc_d = hex_to_rgb(data.get("文字色_暗", "#7ea6d2"))
    tag_d = hex_to_rgb(data.get("tag色_暗", "#afb0bf"))
    bg_d = hex_to_rgb(data.get("tag底板色_暗", "#546c94"))
    gt = hex_to_rgb(data.get("渐变上", "#e5f1ff"))
    gb = hex_to_rgb(data.get("渐变下", "#ffffff"))
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            pipeline.main(tc, tag, bg, tc_d, tag_d, bg_d, gt, gb)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # 打包 output 文件夹为 ZIP
    import zipfile, io as io2
    zip_buf = io2.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        output_dir = pipeline.OUTPUT_DIR
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, output_dir)
                zf.write(fp, arcname)
    zip_buf.seek(0)
    return send_file(zip_buf, mimetype="application/zip",
                     as_attachment=True, download_name="12聊天气泡.zip")


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """关闭服务器（无终端窗口时使用）"""
    import threading, time
    # 先返回响应
    response = jsonify({"ok": True})
    # 再关服务器
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return response


@app.route("/upload_bubble", methods=["POST"])
def upload_bubble():
    """上传素材图片覆盖源文件"""
    ALLOWED = {"left", "right", "bg_0", "bg_1"}
    side = request.form.get("side")
    if side not in ALLOWED:
        return jsonify({"ok": False, "error": f"side 必须为 {ALLOWED}"}), 400
    fname = f"{side}.png" if side.startswith("bg") else f"{side}_.9.png"
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "未上传文件"}), 400
    if not file.filename.endswith(".png"):
        return jsonify({"ok": False, "error": "仅支持 PNG"}), 400
    dest = os.path.join(pipeline.USER_DATA_DIR, fname)
    file.save(dest)
    return jsonify({"ok": True, "file": fname})


if __name__ == "__main__":
    import webbrowser, threading
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5001")).start()
    print("配色工具: http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
