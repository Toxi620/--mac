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

# UI 状态持久化：颜色/文字/字号等存到用户数据目录，重开网页恢复
STATE_FILE = os.path.join(pipeline.USER_DATA_DIR, 'state.json')

_build_version_cache = None


def load_state() -> dict:
    """读取上次的 UI 状态（失败返回空 dict）。"""
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def list_user_files() -> list:
    """用户数据目录里已上传的素材文件名（前端用来标记「已上传」）。"""
    try:
        return sorted(f for f in os.listdir(pipeline.USER_DATA_DIR)
                      if os.path.isfile(os.path.join(pipeline.USER_DATA_DIR, f)))
    except Exception:
        return []


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
            "轮播背景色": h(pipeline.DEFAULT_CAROUSEL_BOARD_BG),
            "气泡底框颜色": h(pipeline.DEFAULT_CAROUSEL_BUBBLE_BG),
            "气泡底框预置色": [h(c) for c in pipeline.CAROUSEL_BUBBLE_PRESETS],
            "编辑字色": h(pipeline.DEFAULT_CAROUSEL_EDIT_COLOR),
            "点赞底部颜色左": h(pipeline.DEFAULT_LIKE_BOTTOM_LEFT),
            "点赞底部颜色右": h(pipeline.DEFAULT_LIKE_BOTTOM_RIGHT),
            "点赞文字色": h(pipeline.DEFAULT_LIKE_TEXT_COLOR),
            "预览底色上": h(pipeline.DEFAULT_PREVIEW_GRAD_TOP),
            "预览底色下": h(pipeline.DEFAULT_PREVIEW_GRAD_BOTTOM)}


@app.after_request
def no_cache(resp):
    """开发用：禁掉 HTML/JS 缓存，避免改完代码刷新看不到变化。

    页面里的预览图是 base64 内联的，本来就不会缓存；但 index.html 本身
    被浏览器缓存住的话，改了模板也看不到效果。
    """
    if not getattr(sys, 'frozen', False):          # 只在本地开发时加
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp


@app.route("/")
def index():
    return render_template("index.html", colors=get_colors(),
                           state=load_state(), user_files=list_user_files(),
                           build_version=get_build_version())


@app.route("/state", methods=["GET"])
def get_state():
    """返回上次保存的 UI 状态 + 已上传素材清单。"""
    return jsonify({"ok": True, "state": load_state(), "files": list_user_files()})


@app.route("/state", methods=["POST"])
def save_state():
    """保存 UI 状态（前端每次改动去抖后调用）。"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "无效数据"}), 400
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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

    # 只打包气泡预览页的产物（商城/动效等其它模块的输出目录不混进来）
    import zipfile, io as io2
    zip_buf = io2.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        output_dir = pipeline.OUTPUT_DIR
        for sub in ['效果', '封面', 'ios', '安卓']:
            root = os.path.join(output_dir, sub)
            if not os.path.isdir(root):
                continue
            for f in os.listdir(root):
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    zf.write(fp, f"{sub}/{f}")
        docx = os.path.join(output_dir, '代码文档.docx')
        if os.path.isfile(docx):
            zf.write(docx, '代码文档.docx')
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
    p = _carousel_and_like_params(request.get_json())
    try:
        imgs = pipeline._generate_carousel(p['tc'], p['wc'], p['bc'], p['bbc'], p['ec'],
                                           p['et'], p['es'], p['src'], p['ud'],
                                           p['tag_c'], p['tag_bg_c'], p['btc'],
                                           p['ll'], p['lr'], p['lt'], p['pt'], p['pb'], p['pvc'], p['pvf'], p['cbc'])
        import base64
        result = {}
        for name, img in imgs.items():
            if name.startswith('_'):
                continue  # 内部键（如 _被赞动效底图）不进预览
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


@app.route("/generate_promo", methods=["POST"])
def generate_promo():
    """气泡宣传预览：左/右气泡分别用各自文案，左对齐/右对齐"""
    data = request.get_json()
    lt = data.get("左文字", "")
    rt = data.get("右文字", "")
    size = int(data.get("字号", 50))
    color = hex_to_rgb(data.get("文字色", "#333333"))
    ios = bool(data.get("ios"))
    try:
        imgs = pipeline._generate_promo(
            left_text=lt, right_text=rt, font_size=size, text_color=color, ios=ios)
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


@app.route("/export_promo", methods=["POST"])
def export_promo():
    """气泡宣传导出：左/右气泡全尺寸 PNG 打包 ZIP"""
    import zipfile
    data = request.get_json()
    lt = data.get("左文字", "")
    rt = data.get("右文字", "")
    size = int(data.get("字号", 50))
    color = hex_to_rgb(data.get("文字色", "#333333"))
    ios = bool(data.get("ios"))
    try:
        imgs = pipeline._generate_promo(
            left_text=lt, right_text=rt, font_size=size, text_color=color, ios=ios)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            suffix = "_IOS" if ios else ""
            for arc, img in [("左气泡%s.png" % suffix, imgs["左侧气泡"]),
                             ("右气泡%s.png" % suffix, imgs["右侧气泡"])]:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                zf.writestr(arc, buf.getvalue())
        zip_buf.seek(0)
        name = "气泡宣传IOS.zip" if ios else "气泡宣传.zip"
        return send_file(zip_buf, mimetype="application/zip",
                         as_attachment=True, download_name=name)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/generate_bubble_preview", methods=["POST"])
def generate_bubble_preview():
    """气泡预览图：470×470 画板，左右气泡各自输入文字"""
    import base64
    data = request.get_json()
    lt = data.get("左文字", "")
    rt = data.get("右文字", "")
    size = int(data.get("字号", pipeline.BUBBLE_PREVIEW_FONT_SIZE))
    color = hex_to_rgb(data.get("文字色", "#333333"))
    try:
        img = pipeline._generate_bubble_preview(lt, rt, size, color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"ok": True, "preview": f"data:image/png;base64,{b64}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/export_bubble_preview", methods=["POST"])
def export_bubble_preview():
    """气泡预览图导出：470×470 全尺寸 PNG"""
    data = request.get_json()
    lt = data.get("左文字", "")
    rt = data.get("右文字", "")
    size = int(data.get("字号", pipeline.BUBBLE_PREVIEW_FONT_SIZE))
    color = hex_to_rgb(data.get("文字色", "#333333"))
    try:
        img = pipeline._generate_bubble_preview(lt, rt, size, color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png",
                         as_attachment=True, download_name="气泡预览图.png")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/upload_preview_bg", methods=["POST"])
def upload_preview_bg():
    """气泡预览图的背景上传（任意尺寸，合成时缩放到 470×470）"""
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "未上传文件"}), 400
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        return jsonify({"ok": False, "error": "仅支持 PNG / JPG"}), 400
    try:
        im = Image.open(file.stream).convert("RGBA")
    except Exception as e:
        return jsonify({"ok": False, "error": f"图片读取失败：{e}"}), 400
    dest = os.path.join(pipeline.USER_DATA_DIR, pipeline.BUBBLE_PREVIEW_BG_NAME)
    im.save(dest)
    return jsonify({"ok": True, "file": pipeline.BUBBLE_PREVIEW_BG_NAME,
                    "size": list(im.size)})


@app.route("/export_carousel", methods=["POST"])
def export_carousel():
    """导出商城轮播图物料 ZIP：根 = 4 张静态画板（被赞相关拆到 /export_like）"""
    p = _carousel_and_like_params(request.get_json())
    try:
        imgs = pipeline._generate_carousel(p['tc'], p['wc'], p['bc'], p['bbc'], p['ec'],
                                           p['et'], p['es'], p['src'], p['ud'],
                                           p['tag_c'], p['tag_bg_c'], p['btc'],
                                           p['ll'], p['lr'], p['lt'], p['pt'], p['pb'], p['pvc'], p['pvf'], p['cbc'])
        out_dir = pipeline.CAROUSEL_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        # 被赞相关已拆到「被赞预览」导出，清掉旧版残留（zip 是整目录打包，不删会混进去）
        stale_names = ['被赞动效.jpg', 'chang.png', 'fang.png']
        for old in os.listdir(out_dir):
            fp = os.path.join(out_dir, old)
            if old in stale_names and os.path.isfile(fp):
                os.remove(fp)
            elif old == '11被赞动效' and os.path.isdir(fp):
                import shutil
                shutil.rmtree(fp)
        for name, img in imgs.items():
            if name.startswith('_'):
                continue  # 内部键不导出
            if name in ('被赞动效.jpg', 'chang.png', 'fang.png'):
                continue  # 移到 /export_like
            if name == '轮播背景色.txt':
                continue  # 这块画板只导色值 txt（下面），图不进包
            save_fmt = 'JPEG' if name.endswith('.jpg') else 'PNG'
            if img.mode == 'RGBA':
                flat = Image.new('RGB', img.size, (255, 255, 255))
                flat.paste(img, mask=img.split()[3])
                flat.save(os.path.join(out_dir, name), format='PNG')
            else:
                img.save(os.path.join(out_dir, name), format=save_fmt)
        # 轮播背景色.txt：内容 = 轮播背景色 hex 小写（如 #ffeef4）
        with open(os.path.join(out_dir, '轮播背景色.txt'), 'w', encoding='utf-8') as f:
            f.write('#' + ''.join('%02x' % c for c in p['cbc']))
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


@app.route("/export_like", methods=["POST"])
def export_like():
    """被赞预览导出 ZIP：被赞动效.jpg + chang.png + fang.png + db#<点赞文字色hex小写>.png"""
    import zipfile
    p = _carousel_and_like_params(request.get_json())
    try:
        imgs = pipeline._generate_carousel(p['tc'], p['wc'], p['bc'], p['bbc'], p['ec'],
                                           p['et'], p['es'], p['src'], p['ud'],
                                           p['tag_c'], p['tag_bg_c'], p['btc'],
                                           p['ll'], p['lr'], p['lt'], p['pt'], p['pb'], p['pvc'], p['pvf'], p['cbc'])
        dbname = 'db#' + ''.join('%02x' % c for c in p['lt']) + '.png'
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in ('被赞动效.jpg', 'chang.png', 'fang.png'):
                img = imgs[name]
                buf = io.BytesIO()
                if name.endswith('.jpg'):
                    if img.mode == 'RGBA':
                        flat = Image.new('RGB', img.size, (255, 255, 255))
                        flat.paste(img, mask=img.split()[3])
                        img = flat
                    img.save(buf, format='JPEG', quality=95)
                else:
                    img.save(buf, format='PNG')
                zf.writestr(name, buf.getvalue())
            # db#<点赞文字色hex小写>.png（206×84 左右渐变）
            buf = io.BytesIO()
            pipeline._gradient_rect(p['ll'], p['lr']).save(buf, format='PNG')
            zf.writestr(dbname, buf.getvalue())
        zip_buf.seek(0)
        return send_file(zip_buf, mimetype="application/zip",
                         as_attachment=True, download_name="11被赞动效.zip")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _carousel_and_like_params(data):
    """从请求 JSON 统一解析轮播色 + 点赞三色，返回传给 _generate_carousel 与 compose_* 的参数。"""
    src = pipeline.CAROUSEL_DIR
    ud = pipeline.USER_DATA_DIR
    tc = hex_to_rgb(data.get("轮播文字色", "#0066ff"))
    wc = hex_to_rgb(data.get("我也想要颜色", "#333333"))
    cbc = hex_to_rgb(data.get("轮播背景色", "#ffedf4"))
    bc = hex_to_rgb(data.get("底框颜色", "#b482d2"))
    bbc = hex_to_rgb(data.get("气泡底框颜色", "#ff8f56"))
    ec = hex_to_rgb(data.get("编辑字色", "#827373"))
    et = data.get("编辑文字", "")
    es = int(data.get("编辑字号", 36))
    tag_c = hex_to_rgb(data.get("tag色", "#979e9c"))
    tag_bg_c = hex_to_rgb(data.get("tag底板色", "#e5fed1"))
    btc = hex_to_rgb(data.get("文字色", "#9f69c5"))
    ll = hex_to_rgb(data.get("点赞底部颜色左", "#fead3a"))
    lr = hex_to_rgb(data.get("点赞底部颜色右", "#ff8f56"))
    lt = hex_to_rgb(data.get("点赞文字色", "#b8a8ca"))
    pt = hex_to_rgb(data.get("预览底色上", "#fefae8"))
    pb = hex_to_rgb(data.get("预览底色下", "#ecfafe"))
    return dict(tc=tc, wc=wc, bc=bc, bbc=bbc, cbc=cbc, ec=ec, et=et, es=es,
                tag_c=tag_c, tag_bg_c=tag_bg_c, btc=btc,
                ll=ll, lr=lr, lt=lt, pt=pt, pb=pb, src=src, ud=ud,
                pvc=(int(data.get("chang偏移X", 0)), int(data.get("chang偏移Y", 0)),
                     int(data.get("chang缩放", 0))),
                pvf=(int(data.get("fang偏移X", 0)), int(data.get("fang偏移Y", 0)),
                     int(data.get("fang缩放", 0))))


@app.route("/generate_gif", methods=["POST"])
def generate_gif():
    """动效预览：主页皮肤.gif + 被赞动效.gif（全尺寸，耗时较长）"""
    import base64
    p = _carousel_and_like_params(request.get_json())
    try:
        static = pipeline._generate_carousel(p['tc'], p['wc'], p['bc'], p['bbc'], p['ec'],
                                             p['et'], p['es'], p['src'], p['ud'],
                                             p['tag_c'], p['tag_bg_c'], p['btc'],
                                             p['ll'], p['lr'], p['lt'], p['pt'], p['pb'], p['pvc'], p['pvf'], p['cbc'])
        home = pipeline.compose_home_gif(static, p['ud'], preview_w=360)
        like = pipeline.compose_like_gif(static, p['ll'], p['lr'], p['lt'], p['src'], p['ud'], preview_w=360)
        result = {}
        for name, raw in list(home.items()) + list(like.items()):
            if name.endswith('.gif'):
                result[name] = "data:image/gif;base64," + base64.b64encode(raw).decode()
        return jsonify({"ok": True, "previews": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/export_gif", methods=["POST"])
def export_gif():
    """导出动效物料 ZIP：主页皮肤.gif / 被赞动效.gif / db#<点赞文字色hex>.png"""
    import zipfile, io as io2
    p = _carousel_and_like_params(request.get_json())
    try:
        static = pipeline._generate_carousel(p['tc'], p['wc'], p['bc'], p['bbc'], p['ec'],
                                             p['et'], p['es'], p['src'], p['ud'],
                                             p['tag_c'], p['tag_bg_c'], p['btc'],
                                             p['ll'], p['lr'], p['lt'], p['pt'], p['pb'], p['pvc'], p['pvf'], p['cbc'])
        home = pipeline.compose_home_gif(static, p['ud'])
        like = pipeline.compose_like_gif(static, p['ll'], p['lr'], p['lt'], p['src'], p['ud'])
        out_dir = os.path.join(pipeline.OUTPUT_DIR, '动效物料')
        os.makedirs(out_dir, exist_ok=True)
        for name, raw in home.items():
            with open(os.path.join(out_dir, name), 'wb') as f:
                f.write(raw)
        for name, obj in like.items():
            if not name.endswith('.gif'):
                continue  # db#xx.png 已移到「导出商城物料」的 11被赞动效/ 里
            with open(os.path.join(out_dir, name), 'wb') as f:
                f.write(obj)
        # 清掉上次导出遗留的 db#*.png 等非 gif，否则会混进这个 zip
        for f in os.listdir(out_dir):
            if not f.endswith('.gif'):
                os.remove(os.path.join(out_dir, f))
        zip_buf = io2.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in os.listdir(out_dir):
                fp = os.path.join(out_dir, f)
                zf.write(fp, f)
        zip_buf.seek(0)
        return send_file(zip_buf, mimetype="application/zip",
                         as_attachment=True, download_name="动效物料.zip")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/upload_carousel", methods=["POST"])
def upload_carousel():
    """上传轮播图素材"""
    ALLOWED = {"头像挂件.png", "方图.png", "star_001_mobile_new.png", "gua#ff5582.png", "主页皮肤.png", "聊天头像.png", "气泡框.gif", "皮肤封面.mp4", "点赞.gif", "预览页gif.png", "轮播预览图.png"}
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


@app.route("/upload_promo_bubble", methods=["POST"])
def upload_promo_bubble():
    """气泡宣传专用的气泡素材上传（安卓/IOS 共用一张 176×176 带 1px 黑边的图）。

    - 存 2 份：`<side>_.9.png`（安卓 / iOS / 气泡预览图 三处共用；iOS 读时自动去 1px 边框）、
      `<side>_promo_src.png`（原图备份）
    - 尺寸不是 176×176 时按「无边框」处理：安卓那份补 1px 透明边框凑够，iOS 那份原样
    """
    import base64
    ALLOWED = {"left", "right"}
    side = request.form.get("side")
    if side not in ALLOWED:
        return jsonify({"ok": False, "error": f"side 必须为 {ALLOWED}"}), 400
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "未上传文件"}), 400
    if not file.filename.endswith(".png"):
        return jsonify({"ok": False, "error": "仅支持 PNG"}), 400
    try:
        im = Image.open(file.stream).convert("RGBA")
    except Exception as e:
        return jsonify({"ok": False, "error": f"图片读取失败：{e}"}), 400

    ud = pipeline.USER_DATA_DIR
    if im.size == (176, 176):
        bordered, borderless = im, im.crop((1, 1, 175, 175))
    else:
        # 不是 176：当成无边框图，安卓那份补一圈 1px 透明边框
        borderless = im
        bordered = Image.new("RGBA", (im.width + 2, im.height + 2), (0, 0, 0, 0))
        bordered.paste(im, (1, 1))

    bordered.save(os.path.join(ud, f"{side}_.9.png"))
    bordered.save(os.path.join(ud, f"{side}_promo_src.png"))

    buf = io.BytesIO()
    bordered.save(buf, format="PNG")
    thumb = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return jsonify({"ok": True, "file": f"{side}_.9.png", "thumb": thumb,
                    "size": list(im.size)})


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
