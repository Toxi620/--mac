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
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import pipeline

app = Flask(__name__)

WORK_DIR = pipeline.WORK_DIR

_build_version_cache = None


def get_build_version() -> str:
    """构建标识：优先 version.txt（打包脚本写入 commit 号），否则 git commit，最后 dev。"""
    global _build_version_cache
    if _build_version_cache is not None:
        return _build_version_cache

    for p in [
        os.path.join(WORK_DIR, 'version.txt'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version.txt'),
    ]:
        try:
            with open(p, encoding='utf-8') as f:
                v = f.read().strip()
            if v:
                _build_version_cache = v
                return v
        except Exception:
            pass

    # 开发环境回退：从 git 读当前 commit
    try:
        import subprocess
        r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                           capture_output=True, text=True, timeout=3,
                           cwd=os.path.dirname(os.path.abspath(__file__)))
        if r.returncode == 0 and r.stdout.strip():
            _build_version_cache = r.stdout.strip() + '-dev'
            return _build_version_cache
    except Exception:
        pass

    _build_version_cache = 'dev'
    return 'dev'


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
            "渐变下": h(pipeline.DEFAULT_GRADIENT_BOTTOM),
            "轮播文字色": h(pipeline.DEFAULT_CAROUSEL_TEXT_COLOR),
            "底框颜色": h(pipeline.DEFAULT_CAROUSEL_BG_COLOR),
            "我也想要颜色": h(pipeline.DEFAULT_CAROUSEL_WANT_COLOR),
            "气泡底框颜色": h(pipeline.DEFAULT_CAROUSEL_BUBBLE_BG),
            "气泡底框预置色": [h(c) for c in pipeline.CAROUSEL_BUBBLE_PRESETS],
            "编辑字色": h(pipeline.DEFAULT_CAROUSEL_EDIT_COLOR)}


@app.route("/")
def index():
    return render_template("index.html", colors=get_colors(), build_version=get_build_version())


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


@app.route("/generate_carousel", methods=["POST"])
def generate_carousel():
    """商城轮播图预览"""
    data = request.get_json()
    tc = hex_to_rgb(data.get("轮播文字色", "#646464"))
    wc = hex_to_rgb(data.get("我也想要颜色", "#333333"))
    bc = hex_to_rgb(data.get("底框颜色", "#646464"))
    bbc = hex_to_rgb(data.get("气泡底框颜色", "#646464"))
    ec = hex_to_rgb(data.get("编辑字色", "#646464"))
    et = data.get("编辑文字", "")
    es = int(data.get("编辑字号", 36))
    tag_c = hex_to_rgb(data.get("tag色", "#979e9c"))
    tag_bg_c = hex_to_rgb(data.get("tag底板色", "#e5fed1"))
    src = pipeline.CAROUSEL_DIR
    ud = pipeline.USER_DATA_DIR
    try:
        # 气泡预览的文字色
        btc = hex_to_rgb(data.get("文字色", "#9f69c5"))
        imgs = pipeline._generate_carousel(tc, wc, bc, bbc, ec, et, es, src, ud, tag_c, tag_bg_c, btc)
        import base64
        result = {}
        for name, img in imgs.items():
            w, h = img.size
            if w > 600:
                r = 600 / w
                img = img.resize((600, round(h * r)), Image.LANCZOS)
            buf = io.BytesIO()
            save_fmt = 'JPEG' if name.endswith('.jpg') else 'PNG'
            img.save(buf, format=save_fmt)
            b64 = base64.b64encode(buf.getvalue()).decode()
            result[name] = f"data:image/{save_fmt.lower()};base64,{b64}"
        return jsonify({"ok": True, "previews": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/generate_ninepatch", methods=["POST"])
def generate_ninepatch():
    """点九验证预览：按点九标准拉伸左/右气泡，内容区绘制苹方文字"""
    data = request.get_json()
    text = data.get("文字", "")
    size = int(data.get("字号", 36))
    color = hex_to_rgb(data.get("文字色", "#333333"))
    try:
        imgs = pipeline._generate_ninepatch(
            text=text, font_size=size, text_color=color)
        import base64
        result = {}
        for name, img in imgs.items():
            w, h = img.size
            if w > 600:
                r = 600 / w
                img = img.resize((600, round(h * r)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            result[name] = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
        return jsonify({"ok": True, "previews": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/export_carousel", methods=["POST"])
def export_carousel():
    """导出商城轮播图文物料 ZIP"""
    data = request.get_json()
    tc = hex_to_rgb(data.get("轮播文字色", "#646464"))
    wc = hex_to_rgb(data.get("我也想要颜色", "#333333"))
    bc = hex_to_rgb(data.get("底框颜色", "#646464"))
    bbc = hex_to_rgb(data.get("气泡底框颜色", "#646464"))
    ec = hex_to_rgb(data.get("编辑字色", "#646464"))
    et = data.get("编辑文字", "")
    es = int(data.get("编辑字号", 36))
    tag_c = hex_to_rgb(data.get("tag色", "#979e9c"))
    tag_bg_c = hex_to_rgb(data.get("tag底板色", "#e5fed1"))
    src = pipeline.CAROUSEL_DIR
    ud = pipeline.USER_DATA_DIR
    try:
        # 气泡预览的文字色
        btc = hex_to_rgb(data.get("文字色", "#9f69c5"))
        imgs = pipeline._generate_carousel(tc, wc, bc, bbc, ec, et, es, src, ud, tag_c, tag_bg_c, btc)
        out_dir = pipeline.CAROUSEL_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        for name, img in imgs.items():
            save_fmt = 'JPEG' if name.endswith('.jpg') else 'PNG'
            if img.mode == 'RGBA':
                flat = Image.new('RGB', img.size, (255, 255, 255))
                flat.paste(img, mask=img.split()[3])
                flat.save(os.path.join(out_dir, name), format='PNG')
            else:
                img.save(os.path.join(out_dir, name), format=save_fmt)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    import zipfile, io as io2
    zip_buf = io2.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(out_dir):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, out_dir)
                zf.write(fp, arcname)
    zip_buf.seek(0)
    return send_file(zip_buf, mimetype="application/zip",
                     as_attachment=True, download_name="商城预览物料.zip")


@app.route("/upload_carousel", methods=["POST"])
def upload_carousel():
    """上传轮播图素材"""
    ALLOWED = {"头像挂件.png", "方图.png", "star_001_mobile_new.png", "gua#ff5582.png", "主页皮肤.png"}
    fname = request.form.get("name")
    if fname not in ALLOWED:
        return jsonify({"ok": False, "error": f"name 必须为 {ALLOWED}"}), 400
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "未上传文件"}), 400
    dest = os.path.join(pipeline.USER_DATA_DIR, fname)
    file.save(dest)
    return jsonify({"ok": True, "file": fname})


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
    import webbrowser, threading, os as _os, socket

    is_frozen = getattr(sys, 'frozen', False)

    # 找可用端口：debug 重载时会重启子进程，用环境变量记住端口避免每次漂移
    port = None
    port_env = _os.environ.get('WALLPAPER_PORT')
    if port_env:
        try:
            port = int(port_env)
        except (TypeError, ValueError):
            port = None
    # 验证端口仍可用，被占用则重新探测
    if port is not None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            s.close()
        except OSError:
            port = None
    if port is None:
        port = 5001
        for _ in range(10):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", port))
                s.close()
                break
            except OSError:
                port += 1
                continue
        else:
            port = 5001  # 都占用了也硬试
    _os.environ['WALLPAPER_PORT'] = str(port)

    url = f"http://localhost:{port}"
    if not is_frozen:
        if not _os.environ.get('WERKZEUG_RUN_MAIN'):
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    else:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    print(f"配色工具: {url}")
    app.run(host="127.0.0.1", port=port, debug=not is_frozen)
