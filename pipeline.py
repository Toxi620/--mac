"""
配色素材图像处理管线
根据配色.txt替换叠加层颜色、点九拉伸聊天气泡、分层合成亮/暗双模式图片。
"""

import os
import re
import sys

from PIL import Image

def _get_work_dir():
    """自动检测工作目录：优先找可执行文件同目录，其次 _MEIPASS，最后脚本所在目录。"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, 'bg_0.png')):
            return exe_dir
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def _get_output_dir():
    """输出目录：用户文档下，确保可写。"""
    home = os.path.expanduser("~")
    d = os.path.join(home, "Documents", "配色工具输出")
    os.makedirs(d, exist_ok=True)
    return d

def _get_data_dir():
    """用户数据目录：存放上传的素材（打包后不能写 bundle）。"""
    home = os.path.expanduser("~")
    d = os.path.join(home, "Documents", "配色工具素材")
    os.makedirs(d, exist_ok=True)
    return d

WORK_DIR = _get_work_dir()
OUTPUT_DIR = _get_output_dir()
USER_DATA_DIR = _get_data_dir()
DIR_EFFECT = os.path.join(OUTPUT_DIR, "效果")  # 页面合成图
DIR_COVER = os.path.join(OUTPUT_DIR, "封面")   # 商城+横幅
DIR_IOS = os.path.join(OUTPUT_DIR, "ios")      # 无边框气泡
DIR_ANDROID = os.path.join(OUTPUT_DIR, "安卓")  # 点九原图复制

# 引流位横幅渐变背景色（上→下）
DEFAULT_GRADIENT_TOP = (229, 241, 255)      # #e5f1ff 浅蓝
DEFAULT_GRADIENT_BOTTOM = (255, 255, 255)   # #ffffff 白

# 商城轮播图颜色
DEFAULT_CAROUSEL_TEXT_COLOR = (0, 122, 255)       # 1~5.png 蓝色
DEFAULT_CAROUSEL_BG_COLOR = (180, 130, 210)       # 底框.png / pic1.png 浅紫
DEFAULT_CAROUSEL_WANT_COLOR = (51, 51, 51)        # 我也想要！.png #333333
DEFAULT_CAROUSEL_BUBBLE_BG = (160, 200, 240)      # 评论气泡底色1/2 浅蓝
DEFAULT_CAROUSEL_EDIT_COLOR = (130, 115, 115)        # 可编辑文字 深灰

def _get_carousel_dir():
    """自动检测商城素材目录：优先 _MEIPASS（打包内），其次 exe 同目录。"""
    if getattr(sys, 'frozen', False):
        p = os.path.join(sys._MEIPASS, '02', '原素材')
        if os.path.exists(p):
            return p
        p = os.path.join(os.path.dirname(sys.executable), '02', '原素材')
        if os.path.exists(p):
            return p
    base = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(base, '..', '02', '原素材'), os.path.join(base, '02', '原素材')]:
        if os.path.exists(p):
            return os.path.abspath(p)
    return os.path.abspath(os.path.join(base, '..', '02', '原素材'))
CAROUSEL_DIR = _get_carousel_dir()
CAROUSEL_OUTPUT_DIR = os.path.join(OUTPUT_DIR, '商城预览物料')

# 暗黑模式色值（来自代码文档.docx，已含10%黑化效果）
TEXT_COLOR_DARK = (126, 166, 210)    # #7ea6d2
TAG_COLOR_DARK = (175, 176, 191)     # #afb0bf
TAG_BG_COLOR_DARK = (84, 108, 148)  # #546c94

# Banner 固定边距规范（无点九边框气泡中，文字距边缘距离）
MARGIN_LEFT = 54
MARGIN_RIGHT = 72
MARGIN_TOP = 54
MARGIN_BOTTOM = 54

# 默认配色（从网页修改，此处为初始值）
DEFAULT_TEXT_COLOR = (159, 105, 197)    # #9f69c5
DEFAULT_TAG_COLOR = (151, 158, 156)     # #979e9c
DEFAULT_TAG_BG_COLOR = (229, 254, 209)  # #e5fed1


# ─── Phase A: 初始化 ─────────────────────────────────────────────

def load_colors(path: str) -> dict:
    """解析配色.txt，返回 {名称: (R,G,B)} 字典。"""
    colors = {}
    pattern = re.compile(r'^(.+?)[：:]\s*#([0-9a-fA-F]{6})$')
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if m:
                name = m.group(1)
                hex_val = m.group(2)
                rgb = (int(hex_val[0:2], 16),
                       int(hex_val[2:4], 16),
                       int(hex_val[4:6], 16))
                colors[name] = rgb
    if len(colors) < 3:
        raise ValueError(f"配色.txt 格式错误，需要至少3行颜色定义，解析到{len(colors)}个")
    return colors


# ─── Phase B: 颜色替换 ────────────────────────────────────────────

def color_replace(im: Image.Image, target_rgb: tuple) -> Image.Image:
    """将所有非透明像素的 RGB 替换为目标色，保留 Alpha。"""
    im = im.convert('RGBA')
    try:
        import numpy as np
        arr = np.array(im)
        mask = arr[:, :, 3] > 0
        arr[mask, 0] = target_rgb[0]
        arr[mask, 1] = target_rgb[1]
        arr[mask, 2] = target_rgb[2]
        return Image.fromarray(arr, 'RGBA')
    except ImportError:
        # NumPy 不可用时的 PIL 回退方案
        im = im.copy()  # 不修改原图
        pixels = im.load()
        w, h = im.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a > 0:
                    pixels[x, y] = (target_rgb[0], target_rgb[1], target_rgb[2], a)
        return im


# ─── 9-Patch 核心 ─────────────────────────────────────────────────

def parse_nine_patch(im: Image.Image) -> dict:
    """
    从点九图的 1px 边框读取拉伸区域和内容 padding。
    返回内部坐标系下的参数（0-based，已减去边框）。
    """
    w, h = im.size
    pixels = im.load()

    def find_black_line(axis_pixels):
        """找连续黑色线段: RGB<50 且 A>200 视为黑线像素。"""
        segments = []
        start = None
        for i, val in enumerate(axis_pixels):
            is_black = val[0] < 50 and val[1] < 50 and val[2] < 50 and val[3] > 200
            if is_black and start is None:
                start = i
            elif not is_black and start is not None:
                segments.append((start, i))
                start = None
        if start is not None:
            segments.append((start, len(axis_pixels)))
        return segments

    # 读取四周边框 (x=0..w-1, y=0) 和 (x=0, y=0..h-1) 等
    top_pixels = [pixels[x, 0] for x in range(w)]
    left_pixels = [pixels[0, y] for y in range(h)]
    bottom_pixels = [pixels[x, h - 1] for x in range(w)]
    right_pixels = [pixels[w - 1, y] for y in range(h)]

    top_segs = find_black_line(top_pixels)
    left_segs = find_black_line(left_pixels)
    bottom_segs = find_black_line(bottom_pixels)
    right_segs = find_black_line(right_pixels)

    if not top_segs or not left_segs:
        raise ValueError("未找到点九拉伸区域标记（顶边/左边无黑线）")

    # 取第一条黑线段作为拉伸区域（内坐标 = 边框坐标 - 1）
    sx = (top_segs[0][0] - 1, top_segs[0][1] - 1)
    sy = (left_segs[0][0] - 1, left_segs[0][1] - 1)

    # 内容 padding（右/下边）
    pad_top = right_segs[0][0] - 1 if right_segs else 0
    pad_bottom = h - 2 - (right_segs[-1][1] - 1) if right_segs else 0
    pad_left = bottom_segs[0][0] - 1 if bottom_segs else 0
    pad_right = w - 2 - (bottom_segs[-1][1] - 1) if bottom_segs else 0

    iw, ih = w - 2, h - 2

    return {
        'stretch_x': sx,
        'stretch_y': sy,
        'fixed_left': sx[0],
        'fixed_right': iw - sx[1],
        'fixed_top': sy[0],
        'fixed_bottom': ih - sy[1],
        'pad_top': pad_top,
        'pad_bottom': pad_bottom,
        'pad_left': pad_left,
        'pad_right': pad_right,
        'internal_w': iw,
        'internal_h': ih,
    }


def nine_patch_scale(im: Image.Image, target_w: int, target_h: int,
                     np_params: dict = None) -> Image.Image:
    """
    对点九图执行九宫格拉伸。
    - np_params=None 时自动从边框检测
    - np_params 传入时复用已有参数
    """
    w, h = im.size

    # 判断是否有 1px 边框：尺寸为 176x176 且左上角透明
    has_border = (w == 176 and h == 176)
    if has_border:
        if np_params is None:
            np_params = parse_nine_patch(im)
        internal = im.crop((1, 1, w - 1, h - 1))
    else:
        if np_params is None:
            raise ValueError("无边框图片必须传入 np_params")
        internal = im.convert('RGBA')

    iw, ih = internal.size
    sx, sy = np_params['stretch_x'], np_params['stretch_y']
    fl, fr = np_params['fixed_left'], np_params['fixed_right']
    ft, fb = np_params['fixed_top'], np_params['fixed_bottom']

    stretch_w = target_w - fl - fr
    stretch_h = target_h - ft - fb
    if stretch_w < 0 or stretch_h < 0:
        raise ValueError(
            f"目标尺寸 {target_w}x{target_h} 小于固定区 {fl + fr}x{ft + fb}")

    # 切 9 块
    patches = {
        'tl': internal.crop((0, 0, sx[0], sy[0])),
        'tc': internal.crop((sx[0], 0, sx[1], sy[0])),
        'tr': internal.crop((sx[1], 0, iw, sy[0])),
        'ml': internal.crop((0, sy[0], sx[0], sy[1])),
        'mc': internal.crop((sx[0], sy[0], sx[1], sy[1])),
        'mr': internal.crop((sx[1], sy[0], iw, sy[1])),
        'bl': internal.crop((0, sy[1], sx[0], ih)),
        'bc': internal.crop((sx[0], sy[1], sx[1], ih)),
        'br': internal.crop((sx[1], sy[1], iw, ih)),
    }

    # 拉伸
    stretchable_keys = {
        'tc': (stretch_w, ft),
        'bc': (stretch_w, fb),
        'ml': (fl, stretch_h),
        'mr': (fr, stretch_h),
        'mc': (stretch_w, stretch_h),
    }
    for key, size in stretchable_keys.items():
        if size[0] > 0 and size[1] > 0:
            patches[key] = patches[key].resize(size, Image.NEAREST)

    # 拼合目标图
    result = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))

    def paste_at(key, x, y):
        """直接复制像素（不带 mask），保持 alpha 不变。"""
        p = patches[key]
        if p.size[0] > 0 and p.size[1] > 0:
            result.paste(p, (x, y))

    paste_at('tl', 0, 0)
    paste_at('tc', fl, 0)
    paste_at('tr', fl + stretch_w, 0)

    paste_at('ml', 0, ft)
    paste_at('mc', fl, ft)
    paste_at('mr', fl + stretch_w, ft)

    paste_at('bl', 0, ft + stretch_h)
    paste_at('bc', fl, ft + stretch_h)
    paste_at('br', fl + stretch_w, ft + stretch_h)

    return result


# ─── 辅助函数 ─────────────────────────────────────────────────────

def darken_overlay(im: Image.Image, opacity: float = 0.1) -> Image.Image:
    """仅对不透明像素（alpha>200）叠加 opacity 全黑，半透明边缘不动。"""
    im = im.convert('RGBA')
    try:
        import numpy as np
        arr = np.array(im)
        mask = arr[:, :, 3] > 200
        factor = 1.0 - opacity
        arr[mask, 0] = (arr[mask, 0].astype(np.float32) * factor).astype(np.uint8)
        arr[mask, 1] = (arr[mask, 1].astype(np.float32) * factor).astype(np.uint8)
        arr[mask, 2] = (arr[mask, 2].astype(np.float32) * factor).astype(np.uint8)
        return Image.fromarray(arr)
    except ImportError:
        # NumPy 不可用时的 PIL 回退
        im = im.copy()  # 不修改原图
        pixels = im.load()
        w, h = im.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a > 200:
                    pixels[x, y] = (int(r * (1 - opacity)),
                                    int(g * (1 - opacity)),
                                    int(b * (1 - opacity)), a)
        return im


def expand_canvas(im: Image.Image, target_w: int, target_h: int,
                  pos: tuple = None) -> Image.Image:
    """将图像居中（或指定位置）放置到更大的画布上。"""
    result = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    if pos:
        x, y = pos
    else:
        x = (target_w - im.width) // 2
        y = (target_h - im.height) // 2
    im = im.convert('RGBA')
    result.paste(im, (x, y), im)
    return result


def composite_scene(bg: Image.Image, bubbles: list, overlays: list) -> Image.Image:
    """分层合成: bg → bubbles → overlays，结果强制不透明。"""
    import numpy as np
    result = bg.convert('RGBA').copy()
    for img, pos in bubbles:
        img = img.convert('RGBA')
        result.paste(img, pos, img)
    for img, pos in overlays:
        img = img.convert('RGBA')
        result.paste(img, pos, img)
    # paste 会混合 alpha，强制整图不透明
    arr = np.array(result)
    arr[:, :, 3] = 255
    return Image.fromarray(arr)


# ─── 主管线 ───────────────────────────────────────────────────────

# ─── 商城轮播图辅助 ───────────────────────────────────────────

def color_replace_simple(im, target_rgb):
    """给半透明素材叠色：保留 alpha，RGB 全部替换为目标色。"""
    im = im.convert('RGBA')
    try:
        import numpy as np
        arr = np.array(im)
        mask = arr[:, :, 3] > 0
        arr[mask, 0] = target_rgb[0]
        arr[mask, 1] = target_rgb[1]
        arr[mask, 2] = target_rgb[2]
        return Image.fromarray(arr)
    except ImportError:
        im = im.copy()
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = px[x, y]
                if a > 0:
                    px[x, y] = (target_rgb[0], target_rgb[1], target_rgb[2], a)
        return im


def paste_at(bg, overlay, x, y, w=None, h=None):
    """粘贴 overlay 到 bg 的 (x,y)，可选缩放到 (w,h)。"""
    if overlay is None:
        return bg
    img = overlay.convert('RGBA')
    if w and h:
        img = img.resize((w, h), Image.LANCZOS)
    bg.paste(img, (x, y), img)
    return bg


def _generate_carousel(text_color, want_color, bg_color, bubble_bg_color,
                       edit_color, edit_text, src_dir, user_dir,
                       car_tag_color=None, car_tag_bg_color=None, car_text_color=None):
    """生成 5 张商城轮播图，返回 {(文件名): Image}。"""
    from PIL import ImageFont, ImageDraw

    def load_src(n):
        return Image.open(os.path.join(src_dir, n)).convert('RGBA')

    def load_color(n, c, sub='改颜色的'):
        p = os.path.join(src_dir, sub, n)
        if not os.path.exists(p):
            p = os.path.join(src_dir, n)
        return color_replace_simple(Image.open(p).convert('RGBA'), c)

    def load_user(n):
        # 优先用户上传，没有则用默认素材
        p = os.path.join(user_dir, n)
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
        p = os.path.join(src_dir, '塞进去替换的', n)
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
        return None

    def draw_edit_text(img):
        """在所有图片相同位置绘制编辑文字"""
        if not edit_text:
            return
        try:
            font = ImageFont.truetype('/System/Library/Fonts/PingFangSC-Medium.otf', 36)
        except:
            try:
                font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 36)
            except:
                font = ImageFont.load_default()
        draw = ImageDraw.Draw(img)
        draw.text((625, 2220), edit_text, fill=edit_color + (255,), font=font, anchor="mm")

    result = {}

    # 编辑文字通用
    def make_with_text(bg_fn):
        bg = bg_fn()
        draw_edit_text(bg)
        return bg

    # 底框（5张图统一位置）
    def apply_base(img):
        return paste_at(img, load_color('底框.png', bg_color), 362, 2079)

    # ---- (1) 主页皮肤.png ----
    def img1():
        bg = apply_base(load_src('主页皮肤.png'))
        bg = paste_at(bg, load_color('1.png', text_color), 507, 2120)
        return bg
    result['主页皮肤.png'] = make_with_text(img1)

    # ---- (2) 卡片背景.png ----
    def img2():
        bg = apply_base(load_src('卡片背景.png'))
        bg = paste_at(bg, load_user('头像挂件.png'), 33, 310, 135, 143)
        bg = paste_at(bg, load_src('V标.png'), 131, 408)
        bg = paste_at(bg, load_user('方图.png'), 43, 644, 572, 573)
        bg = paste_at(bg, load_user('star_001_mobile_new.png'), 834, 288, 282, 125)
        bg = paste_at(bg, load_color('我也想要！.png', want_color), 191, 1761)
        bg = paste_at(bg, load_color('pic1.png', bubble_bg_color), 169, 1744)
        bg = paste_at(bg, load_color('2.png', text_color), 507, 2120)
        return bg
    result['卡片背景.png'] = make_with_text(img2)

    # ---- (3) 评论气泡.png ----
    def img3():
        bg = apply_base(load_src('评论气泡.png'))
        bg = paste_at(bg, load_color('评论气泡底色2.png', bubble_bg_color), 171, 570)
        bg = paste_at(bg, load_color('评论气泡底色1.png', bubble_bg_color), 413, 1087)
        bg = paste_at(bg, load_color('评论气泡-我也想要！.png', want_color), 446, 1115)
        gua = load_user('gua#ff5582.png')
        bg = paste_at(bg, gua, 505, 616, 139, 54)
        bg = paste_at(bg, gua, 639, 1145)
        bg = paste_at(bg, load_color('3.png', text_color), 507, 2120)
        return bg
    result['评论气泡.png'] = make_with_text(img3)

    # ---- (4) 聊天气泡.png ----
    def img4():
        bt = car_text_color if car_text_color is not None else DEFAULT_TEXT_COLOR
        tc = car_tag_color if car_tag_color is not None else DEFAULT_TAG_COLOR
        tbc = car_tag_bg_color if car_tag_bg_color is not None else DEFAULT_TAG_BG_COLOR

        # 1242x2688 透明画布（超出部分自动裁剪）
        bg = Image.new('RGBA', (1242, 2688), (0, 0, 0, 0))

        # 页面1 缩放到 1242x2691，放在 (0,28)，底部自动裁剪
        page1_src = _generate_core(bt, tc, tbc, WORK_DIR,
            None, None, None, None, None)["页面1普通模式"].copy()
        page1_src = page1_src.resize((1242, 2691), Image.LANCZOS)
        bg.paste(page1_src, (0, 28))

        # 替换 lj_0 → 小助理的AI回复 (tag色), sk_0 → 链接高亮 (tag底板色)
        scale = 1242 / 1290
        def sp(x, y): return (int(x * scale), int(y * scale))
        ai = color_replace_simple(
            load_src(os.path.join('改颜色的', '小助理的AI回复.png')), tc)
        link = color_replace_simple(
            load_src(os.path.join('改颜色的', '链接高亮.png')), tbc)
        bg.paste(link, sp(212, 724), link)
        bg.paste(ai, sp(220, 734), ai)

        # 聊天气泡头像/中/上
        bg = paste_at(bg, load_src('聊天气泡头像.png'), 0, 0)
        bg = paste_at(bg, load_src('聊天气泡中.png'), 0, 0)
        bg = paste_at(bg, load_src('聊天气泡上.png'), 0, 890)

        # 底框 (和其他4张图相同位置，不缩放)
        bg = paste_at(bg, load_color('底框.png', bg_color), 362, 2079)

        # 气泡点九图 759x207
        left_9_path = os.path.join(src_dir, '..', '..', '打包', 'left_.9.png')
        if not os.path.exists(left_9_path):
            left_9_path = os.path.join(WORK_DIR, 'left_.9.png')
        if os.path.exists(left_9_path):
            left_9 = Image.open(left_9_path).convert('RGBA')
            np_left = parse_nine_patch(left_9)
            bubble = nine_patch_scale(left_9, 759, 207, np_left)
            bg.paste(bubble, (324, 1123), bubble)

        bg = paste_at(bg, load_color('会员上新了，快去抢！.png', bt), 383, 1193)
        bg = paste_at(bg, load_color('4.png', text_color), 507, 2120)
        return bg
    result['聊天气泡.png'] = make_with_text(img4)

    # ---- (5) 卡片背景.png → 被赞动效.jpg ----
    def img5():
        bg = apply_base(load_src('卡片背景.png'))
        bg = paste_at(bg, load_user('头像挂件.png'), 33, 310, 135, 143)
        bg = paste_at(bg, load_src('V标.png'), 131, 408)
        bg = paste_at(bg, load_user('方图.png'), 43, 644, 572, 573)
        bg = paste_at(bg, load_user('star_001_mobile_new.png'), 834, 288, 282, 125)
        bg = paste_at(bg, load_color('我也想要！.png', want_color), 191, 1761)
        bg = paste_at(bg, load_color('pic1.png', bubble_bg_color), 169, 1744)
        bg = paste_at(bg, load_color('5.png', text_color), 507, 2120)
        return bg
    bg5 = img5()
    draw_edit_text(bg5)
    bg5_rgb = Image.new('RGB', bg5.size, (255, 255, 255))
    bg5_rgb.paste(bg5, mask=bg5.split()[3] if bg5.mode == 'RGBA' else None)
    result['被赞动效.jpg'] = bg5_rgb

    return result


def _save_colors(path, tc, tag, bg):
    """将颜色写回配色.txt"""
    lines = [
        f"文字色：#{tc[0]:02x}{tc[1]:02x}{tc[2]:02x}",
        f"tag色：#{tag[0]:02x}{tag[1]:02x}{tag[2]:02x}",
        f"tag底板色：#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}",
    ]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def _generate_core(text_color, tag_color, tag_bg_color, workdir,
                   text_color_dark=None, tag_color_dark=None, tag_bg_color_dark=None,
                   gradient_top=None, gradient_bottom=None) -> dict:
    """核心处理：加载 → 颜色替换 → 点九 → 合成，返回所有中间/最终图像的字典。"""
    def load(name):
        """优先读用户上传的素材，没有再读打包目录。"""
        user_path = os.path.join(USER_DATA_DIR, name)
        if os.path.exists(user_path):
            return Image.open(user_path).convert('RGBA')
        return Image.open(os.path.join(workdir, name)).convert('RGBA')

    bg_0 = load('bg_0.png')
    bg_1 = load('bg_1.png')
    wz_0 = load('wz_0.png')
    lj_0 = load('lj_0.png')
    sk_0 = load('sk_0.png')
    left_9 = load('left_.9.png')
    right_9 = load('right_.9.png')

    # Phase B: 颜色替换
    wz_replaced = color_replace(wz_0, text_color)
    lj_replaced = color_replace(lj_0, tag_color)
    sk_replaced = color_replace(sk_0, tag_bg_color)
    # 商城6字展示文字素材（染文字色，叠到气泡上预览用，不导出）
    shop_src_path = os.path.join(workdir, '商城6字展示420X174.png')
    user_shop = os.path.join(USER_DATA_DIR, '商城6字展示420X174.png')
    if os.path.exists(user_shop):
        shop_src_path = user_shop
    shop_text_img = None
    if os.path.exists(shop_src_path):
        shop_src = Image.open(shop_src_path).convert('RGBA')
        shop_text_img = color_replace(shop_src, text_color)

    # Phase C: 亮色模式
    np_left = parse_nine_patch(left_9)
    np_right = parse_nine_patch(right_9)
    bubbles_normal = [
        (nine_patch_scale(right_9, 713, 182, np_right), (403, 324)),
        (nine_patch_scale(right_9, 713, 182, np_right), (403, 906)),
        (nine_patch_scale(left_9, 981, 376, np_left), (170, 509)),
        (nine_patch_scale(left_9, 779, 182, np_left), (170, 1092)),
    ]
    overlays_normal = [(wz_replaced, (0, 0)), (sk_replaced, (0, 0)), (lj_replaced, (0, 0))]
    scene_normal = composite_scene(bg_0, bubbles_normal, overlays_normal)

    # Phase D: 暗黑模式（使用独立暗色值，未传则默认亮色叠10%黑）
    if text_color_dark is None:
        text_color_dark = TEXT_COLOR_DARK
        tag_color_dark = TAG_COLOR_DARK
        tag_bg_color_dark = TAG_BG_COLOR_DARK
    wz_dark = color_replace(wz_0, text_color_dark)
    lj_dark = color_replace(lj_0, tag_color_dark)
    sk_dark = color_replace(sk_0, tag_bg_color_dark)
    left_night = darken_overlay(left_9, 0.1)
    right_night = darken_overlay(right_9, 0.1)
    bubbles_dark = [
        (nine_patch_scale(right_night, 713, 182, np_right), (403, 324)),
        (nine_patch_scale(right_night, 713, 182, np_right), (403, 906)),
        (nine_patch_scale(left_night, 981, 376, np_left), (170, 509)),
        (nine_patch_scale(left_night, 779, 182, np_left), (170, 1092)),
    ]
    overlays_dark = [(wz_dark, (0, 0)), (sk_dark, (0, 0)), (lj_dark, (0, 0))]
    scene_dark = composite_scene(bg_1, bubbles_dark, overlays_dark)

    left_night_borderless = left_night.crop((1, 1, left_night.width - 1, left_night.height - 1))
    right_night_borderless = right_night.crop((1, 1, right_night.width - 1, right_night.height - 1))

    # Phase E: 商城展示图（气泡 + 文字叠加）
    shop = nine_patch_scale(left_9, 420, 174, np_left)
    shop_with_text = shop.copy() if shop_text_img is not None else None
    if shop_text_img is not None:
        shop_with_text.paste(shop_text_img, (0, 0), shop_text_img)

    # Phase F: 引流位横幅
    if gradient_top is None:
        gradient_top = DEFAULT_GRADIENT_TOP
        gradient_bottom = DEFAULT_GRADIENT_BOTTOM
    banner_img = None
    wz_3_path = os.path.join(workdir, 'wz_3.png')
    user_wz3 = os.path.join(USER_DATA_DIR, 'wz_3.png')
    if os.path.exists(user_wz3):
        wz_3_path = user_wz3
    if os.path.exists(wz_3_path):
        wz_3 = Image.open(wz_3_path).convert('RGBA')
        wz_3_replaced = color_replace(wz_3, text_color)
        bbox = wz_3_replaced.getbbox()
        if bbox:
            # 裁剪出文字区域（去掉大图的空白边缘）
            wz_3_text = wz_3_replaced.crop(bbox)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            bubble_w, bubble_h = 253, 176
            pad_l, pad_r = np_left['pad_left'], np_left['pad_right']
            pad_t, pad_b = np_left['pad_top'], np_left['pad_bottom']
            content_w = bubble_w - pad_l - pad_r
            content_h = bubble_h - pad_t - pad_b

            # 生成气泡
            bubble = nine_patch_scale(left_9, bubble_w, bubble_h, np_left)

            # 文字居中在气泡内容区内
            text_x = pad_l + (content_w - tw) // 2
            text_y = pad_t + (content_h - th) // 2
            bubble.paste(wz_3_text, (text_x, text_y), wz_3_text)

            # 渐变背景（上→下）
            import numpy as np
            banner_img = Image.new('RGBA', (366, 204), (0, 0, 0, 0))
            arr = np.array(banner_img)
            for y in range(204):
                t = y / 203.0  # 0.0→1.0
                r = int(gradient_top[0] * (1 - t) + gradient_bottom[0] * t)
                g = int(gradient_top[1] * (1 - t) + gradient_bottom[1] * t)
                b = int(gradient_top[2] * (1 - t) + gradient_bottom[2] * t)
                arr[y, :, 0] = r
                arr[y, :, 1] = g
                arr[y, :, 2] = b
                arr[y, :, 3] = 255
            banner_img = Image.fromarray(arr)

            # 气泡居中放在渐变背景上
            bx = (366 - bubble_w) // 2
            by = (204 - bubble_h) // 2
            banner_img.paste(bubble, (bx, by), bubble)

    return {
        "页面1普通模式": scene_normal,
        "页面2暗黑模式": scene_dark,
        "left_night": left_night_borderless,
        "right_night": right_night_borderless,
        "商城6字展示420X174": shop,
        "商城6字展示420X174(预览)": shop_with_text if shop_with_text else shop,
        "引流位banner": banner_img,
        "_np_left": np_left,
        "_np_right": np_right,
        "_left_9": left_9,
        "_right_9": right_9,
    }


def main(text_color=None, tag_color=None, tag_bg_color=None,
         text_color_dark=None, tag_color_dark=None, tag_bg_color_dark=None,
         gradient_top=None, gradient_bottom=None):
    """主管线（全量高清输出）。"""
    workdir = WORK_DIR
    for d in [OUTPUT_DIR, DIR_EFFECT, DIR_COVER, DIR_IOS, DIR_ANDROID]:
        os.makedirs(d, exist_ok=True)

    # Phase A: 读配色
    if text_color is None:
        print("[Phase A] 使用默认配色...")
        text_color = DEFAULT_TEXT_COLOR
        tag_color = DEFAULT_TAG_COLOR
        tag_bg_color = DEFAULT_TAG_BG_COLOR
    print(f"  文字色={text_color}, tag色={tag_color}, tag底板色={tag_bg_color}")

    # 核心处理
    imgs = _generate_core(text_color, tag_color, tag_bg_color, workdir,
                          text_color_dark, tag_color_dark, tag_bg_color_dark,
                          gradient_top, gradient_bottom)

    # 保存
    imgs["页面1普通模式"].save(os.path.join(DIR_EFFECT, '页面1普通模式.png'))
    print("  → 页面1普通模式.png")
    imgs["页面2暗黑模式"].save(os.path.join(DIR_EFFECT, '页面2暗黑模式.png'))
    print("  → 页面2暗黑模式.png")
    imgs["left_night"].save(os.path.join(DIR_IOS, 'left_night.png'))
    imgs["right_night"].save(os.path.join(DIR_IOS, 'right_night.png'))
    print("  → left_night.png / right_night.png (borderless)")
    imgs["商城6字展示420X174"].save(os.path.join(DIR_COVER, '商城6字展示420X174.png'))
    print("  → 商城6字展示420X174.png")
    if imgs["引流位banner"]:
        imgs["引流位banner"].save(os.path.join(DIR_COVER, '引流位banner.png'))
        print("  → 引流位banner.png")
    else:
        print("  [跳过] 引流位banner (无wz_3.png)")

    # 安卓复制（优先用用户上传的素材）
    import shutil
    for fname in ['left_.9.png', 'right_.9.png']:
        src = os.path.join(USER_DATA_DIR, fname)
        if not os.path.exists(src):
            src = os.path.join(workdir, fname)
        shutil.copy2(src, os.path.join(DIR_ANDROID, fname))
    print("  → 安卓/ 复制完成")

    # docx
    docx_src = os.path.join(workdir, '代码文档.docx')
    user_docx = os.path.join(USER_DATA_DIR, '代码文档.docx')
    if os.path.exists(user_docx):
        docx_src = user_docx
    docx_dst = os.path.join(OUTPUT_DIR, '代码文档.docx')
    docx_tmp = docx_dst + '.tmp'
    if os.path.exists(docx_src):
        import zipfile, tempfile, shutil as sh
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(docx_src, 'r') as z:
            z.extractall(tmp)
        xml_path = os.path.join(tmp, 'word', 'document.xml')
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml = f.read()
        def rgb_to_hex(rgb):
            return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
        for old, new in {
            '#6985c5': rgb_to_hex(text_color),
            '#97979e': rgb_to_hex(tag_color),
            '#d1e2fe': rgb_to_hex(tag_bg_color),
        }.items():
            xml = xml.replace(old, new)
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml)
        with zipfile.ZipFile(docx_tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmp):
                for f in files:
                    zout.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), tmp))
        sh.rmtree(tmp)
        if os.path.exists(docx_dst):
            try: os.remove(docx_dst)
            except: pass
        try: os.rename(docx_tmp, docx_dst)
        except: docx_dst = docx_tmp
        print("  → 代码文档.docx 已生成")
    else:
        print("  [注意] 未找到模板 docx，跳过")

    print("\n全部完成!")


def preview(text_color, tag_color, tag_bg_color,
            text_color_dark=None, tag_color_dark=None, tag_bg_color_dark=None,
            gradient_top=None, gradient_bottom=None) -> dict:
    """缩略预览：生成 6 张缩略图（宽 600px），返回 {name: base64}。"""
    imgs = _generate_core(text_color, tag_color, tag_bg_color, WORK_DIR,
                          text_color_dark, tag_color_dark, tag_bg_color_dark,
                          gradient_top, gradient_bottom)
    import base64, io
    result = {}
    for key in ["页面1普通模式", "页面2暗黑模式", "商城6字展示420X174(预览)", "引流位banner", "left_night", "right_night"]:
        img = imgs[key]
        if img is None:
            continue
        # 缩放到宽 600px
        w, h = img.size
        if w > 600:
            ratio = 600 / w
            img = img.resize((600, round(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        result[key] = f"data:image/png;base64,{b64}"
    return result


if __name__ == '__main__':
    main()
