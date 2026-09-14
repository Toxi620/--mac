"""
配色素材图像处理管线
根据配色.txt替换叠加层颜色、点九拉伸聊天气泡、分层合成亮/暗双模式图片。
"""

import math
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

# 04/原始矩形位置/left_.9.png 的红框（内容区），源图内部坐标（已去 1px 点九边框）
# 中心相对 176 外框中心 = (-17,-1)。换左气泡素材时按对应参考图重测即可。
PINK_LEFT_BOX = (11, 26, 128, 145)

# 商城轮播图颜色
DEFAULT_CAROUSEL_TEXT_COLOR = (0, 122, 255)       # 1~5.png 蓝色
DEFAULT_CAROUSEL_BG_COLOR = (180, 130, 210)       # 底框.png / pic1.png 浅紫
DEFAULT_CAROUSEL_WANT_COLOR = (51, 51, 51)        # 我也想要！.png #333333
# 气泡底框五选一预置色
CAROUSEL_BUBBLE_PRESETS = [
    (255, 143, 86),    # #FF8F56 橙
    (254, 173, 58),    # #FEAD3A 琥珀
    (222, 200, 76),    # #DEC84C 黄
    (165, 93, 171),    # #A55DAB 紫
    (208, 70, 102),    # #D04666 玫红
]
DEFAULT_CAROUSEL_BUBBLE_BG = CAROUSEL_BUBBLE_PRESETS[0]  # 默认 #FF8F56
DEFAULT_CAROUSEL_EDIT_COLOR = (130, 115, 115)        # 可编辑文字 深灰
DEFAULT_CAROUSEL_EDIT_SIZE = 36                      # 可编辑文字字号

def _get_carousel_dir():
    """自动检测商城素材目录：优先打包内 _MEIPASS，其次 exe/脚本同目录。"""
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(sys._MEIPASS, '原素材'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), '原素材'))
    base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base, '原素材'))
    candidates.append(os.path.join(base, '..', '02', '原素材'))
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    return candidates[0]
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

# 动效gif 点赞相关默认色
DEFAULT_LIKE_BOTTOM_LEFT = (254, 173, 58)   # 点赞底部颜色左  #fead3a
DEFAULT_LIKE_BOTTOM_RIGHT = (255, 143, 86)  # 点赞底部颜色右  #ff8f56
DEFAULT_LIKE_TEXT_COLOR = (184, 168, 202)   # 点赞文字色      #b8a8ca
GIF_MAX_BYTES = 8 * 1024 * 1024             # 单张 gif 超过即压缩


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


def map_rect_np(np_params: dict, box: tuple, out_w: int, out_h: int) -> tuple:
    """把源图内部坐标里的矩形 box=(x0,y0,x1,y1) 按点九拉伸映射到 out_w×out_h 的气泡里。

    映射规则与 nine_patch_scale 完全一致：左/上固定区不动、中间拉伸区等比放大、
    右/下固定区整体平移。返回映射后的框 (x0,y0,x1,y1)（浮点）。
    """
    iw, ih = np_params['internal_w'], np_params['internal_h']
    fl, fr = np_params['fixed_left'], np_params['fixed_right']
    ft, fb = np_params['fixed_top'], np_params['fixed_bottom']
    sw = (iw - fl - fr) or 1
    sh = (ih - ft - fb) or 1
    ow = out_w - fl - fr
    oh = out_h - ft - fb

    def mx(x):
        if x < fl:
            return x
        elif x <= fl + sw:
            return fl + (x - fl) * (ow / sw)
        return fl + ow + (x - fl - sw)

    def my(y):
        if y < ft:
            return y
        elif y <= ft + sh:
            return ft + (y - ft) * (oh / sh)
        return ft + oh + (y - ft - sh)

    return (mx(box[0]), my(box[1]), mx(box[2]), my(box[3]))


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
                       edit_color, edit_text, edit_size, src_dir, user_dir,
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

    def load_override(n):
        # 优先用户上传的背景大图，否则用默认素材（原素材根目录）
        p = os.path.join(user_dir, n)
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
        return load_src(n)

    # ---- 聊天头像：裁透明边 → 圆形粘贴（形如 03/椭圆 7.png，圆内切于正方形）----
    _avatar_cropped = None  # 缓存"裁透明边后"的内容图；False 表示无上传

    def get_avatar():
        """加载并缓存用户上传的聊天头像（裁掉四周透明像素）。没上传返回 None。"""
        nonlocal _avatar_cropped
        if _avatar_cropped is None:
            im = load_user('聊天头像.png')
            if im is None:
                _avatar_cropped = False
            else:
                box = im.getbbox()
                if box and box[2] > box[0] and box[3] > box[1]:
                    _avatar_cropped = im.crop(box)
                else:
                    _avatar_cropped = False
        return _avatar_cropped if _avatar_cropped is not False else None

    def paste_avatar(bg, x, y, wh):
        """把聊天头像盖成直径=wh 的圆贴到 bg：(x,y)=外接正方形左上角。无上传则跳过。"""
        im = get_avatar()
        if im is None:
            return bg
        cw, ch = im.size
        k = wh / min(cw, ch)  # cover：等比放大到铺满 wh×wh
        if abs(k - 1) > 1e-9:
            im = im.resize((max(1, int(round(cw * k))),
                            max(1, int(round(ch * k)))), Image.LANCZOS)
        nw, nh = im.size
        l, t = (nw - wh) // 2, (nh - wh) // 2
        im = im.crop((l, t, l + wh, t + wh))
        # 圆形 alpha 蒙版（2x 超采样抗锯齿）
        s = wh * 2
        mask = Image.new('L', (s, s), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
        mask = mask.resize((wh, wh), Image.LANCZOS)
        out = Image.new('RGBA', (wh, wh), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        bg.paste(out, (x, y), out)
        return bg

    def draw_edit_text(img):
        """在所有图片相同位置绘制编辑文字"""
        if not edit_text:
            return
        font = None
        bundled = os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf')
        for fp in [bundled, 'C:/Windows/Fonts/msyh.ttc']:
            try:
                font = ImageFont.truetype(fp, edit_size)
                break
            except:
                continue
        if font is None:
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
        bg = apply_base(load_override('主页皮肤.png'))
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
        # 需求新增：用户聊天头像(圆形)+1.png
        bg = paste_avatar(bg, 37, 1679, 118)
        bg = paste_at(bg, load_src('1.png'), 111, 1754)
        bg = paste_at(bg, load_color('2.png', text_color), 507, 2120)
        return bg
    result['卡片背景.png'] = make_with_text(img2)

    # ---- (3) 评论气泡.png ----
    def img3():
        # 底图换为需求新素材"图层 1086.png"
        bg = apply_base(load_src('图层 1086.png'))
        # 需求新增，严格照 txt 顺序自下而上贴
        bg = paste_avatar(bg, 40, 1074, 116)
        bg = paste_at(bg, load_src('评论放大.png'), 0, 774)
        bg = paste_avatar(bg, 212, 998, 170)
        bg = paste_at(bg, load_src('图层 1088.png'), 319, 1106)
        # 评论气泡底色要压在「评论放大」之上（它的不透明区 y969..1258 会盖掉
        # y1087 的底色1），但要垫在「我也想要」和气泡装饰之下。
        bg = paste_at(bg, load_color('评论气泡底色2.png', bubble_bg_color), 171, 570)
        bg = paste_at(bg, load_color('评论气泡底色1.png', bubble_bg_color), 413, 1087)
        # 「我也想要」+ 气泡装饰必须压在最顶：
        # 评论放大.png 的不透明区在 y969..1258，贴在 (0,774) 会把 y1115 的文字
        # 和 y1145 的装饰盖掉，所以这两样放到新增组件之后再贴。
        gua = load_user('gua#ff5582.png')
        bg = paste_at(bg, gua, 505, 616, 139, 54)
        bg = paste_at(bg, gua, 639, 1145)
        bg = paste_at(bg, load_color('评论气泡-我也想要！.png', want_color), 446, 1115)
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

        # 聊天气泡头像/中/上；叠层按需求：头像.png → 头像(2处) → 上.png → 上头像
        bg = paste_at(bg, load_src('聊天气泡头像.png'), 0, 0)
        bg = paste_at(bg, load_src('聊天气泡中.png'), 0, 0)
        bg = paste_avatar(bg, 34, 540, 122)
        bg = paste_avatar(bg, 34, 1103, 122)
        bg = paste_at(bg, load_src('聊天气泡上.png'), 0, 890)
        bg = paste_avatar(bg, 161, 890 + 253, 165)

        # 底框 (和其他4张图相同位置，不缩放)
        bg = paste_at(bg, load_color('底框.png', bg_color), 362, 2079)

        # 气泡点九图 759x207（优先用户上传的 left_.9.png，与气泡预览一致）
        left_9 = None
        user_left = os.path.join(user_dir, 'left_.9.png')
        if os.path.exists(user_left):
            left_9 = Image.open(user_left).convert('RGBA')
        else:
            left_9_path = os.path.join(src_dir, '..', '..', '打包', 'left_.9.png')
            if not os.path.exists(left_9_path):
                left_9_path = os.path.join(WORK_DIR, 'left_.9.png')
            if os.path.exists(left_9_path):
                left_9 = Image.open(left_9_path).convert('RGBA')
        if left_9 is not None:
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
        # 需求新增：用户聊天头像(圆形)+1.png（与卡片背景页一致）
        bg = paste_avatar(bg, 37, 1679, 118)
        bg = paste_at(bg, load_src('1.png'), 111, 1754)
        bg = paste_at(bg, load_color('5.png', text_color), 507, 2120)
        return bg
    bg5 = img5()
    draw_edit_text(bg5)
    bg5_rgb = Image.new('RGB', bg5.size, (255, 255, 255))
    bg5_rgb.paste(bg5, mask=bg5.split()[3] if bg5.mode == 'RGBA' else None)
    result['被赞动效.jpg'] = bg5_rgb

    return result


def _generate_promo(left_text='', right_text='', font_size=50,
                    text_color=(51, 51, 51), ios=False):
    """气泡宣传：按点九生成左/右气泡。

    两套完全独立的素材与留白配置（`ios=False` 安卓 / `ios=True` IOS）：
    - **安卓**（已冻结）：源图 `left_.9.png` / `right_.9.png`（176×176，带 1px 点九黑边），
      留白从**黑线框**往里量，常量 `PROMO_*` / `PROMO_L_*`
    - **IOS**：读**同一份** `left_.9.png` / `right_.9.png`，`load_9()` 里自动去 1px 黑边，
      点九参数按规格手写（拉伸区第82格/第106格），文字留白用 `PROMO_IOS_TEXT_*`

    公共逻辑（两套一致）：
    - 换行：手动 `\\n` 优先，超长自动折行，带标点禁则
    - 文字：中文 Noto Sans SC Light / 英文 Noto Sans Light（都是开源），逐字符渲染；字号默认 50；
      字间距 `PROMO_LETTER_SPACING`、行高系数 `PROMO_LINE_H_RATIO`
    - 左右气泡一律左对齐到内容框左缘
    - 限宽：安卓看 `PROMO_MAX_BUBBLE_W`（气泡总宽），IOS 看 `PROMO_IOS_MAX_W`
    - 右侧留白退让：先用「不换行档」，放不下退让到「换行档」，仍放不下才折行
    - 下限 = 素材本身尺寸
    返回 {"左侧气泡": Image, "右侧气泡": Image}。
    """
    from PIL import ImageDraw, ImageFont

    def load_9(n):
        p = os.path.join(USER_DATA_DIR, n)
        if os.path.exists(p):
            im = Image.open(p).convert('RGBA')
        else:
            im = Image.open(os.path.join(WORK_DIR, n)).convert('RGBA')
        # iOS 用无黑边的图：用户上传的是 176 带边框的，这里统一去掉那 1px
        if ios and im.size == (176, 176):
            im = im.crop((1, 1, 175, 175))
        return im

    def _opaque_box(im):
        """气泡实体（不透明像素）包围盒，返回 (左, 右, 上, 下)，与黑线框同口径。

        iOS 素材没有点九黑线，用实体范围当「内容区基准」。
        getbbox() 给的是 (left, upper, right, lower)，这里转成 (l, r, t, b)。
        """
        bb = im.split()[3].getbbox()
        if not bb:
            return 0, im.width, 0, im.height
        left, upper, right, lower = bb
        return left, right, upper, lower

    def _load_font(paths, size):
        """按候选列表找第一个能用的字体。"""
        for fp in paths:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def load_font(size):
        """中文 = SimSun（Windows 中易宋体），英文/数字 = Arial。返回 (cn, en)。"""
        return _load_font(PROMO_FONT_CN, size), _load_font(PROMO_FONT_EN, size)

    def is_ascii(ch):
        """英文/数字/半角符号走 Arial，其余（中文、全角）走 SimSun。"""
        return ord(ch) < 0x2E80

    def char_font(ch, cn_font, en_font):
        return en_font if is_ascii(ch) else cn_font

    def text_width(s, cn_font, en_font):
        """整段宽度 = 逐字符按所属字体累加 + 字间距（混排不能直接用 getlength）。

        每个字符后面都算一次字距，与 split_runs 的推进方式保持一致。
        iOS 的字间距独立（PROMO_IOS_LETTER_SPACING）。
        """
        sp = PROMO_IOS_LETTER_SPACING if ios else PROMO_LETTER_SPACING
        return sum(char_font(ch, cn_font, en_font).getlength(ch) + sp for ch in s)

    def split_runs(s, cn_font, en_font):
        """按字体把字符串切成若干段，返回 [(font, 文字, 起点x偏移)]。

        段内字符按各自字宽 + 字间距推进；同字体的连续字符合并成一段渲染
        （字距通过每段内部的逐字定位实现，所以这里按「逐字符位置」切段）。
        """
        sp = PROMO_IOS_LETTER_SPACING if ios else PROMO_LETTER_SPACING
        runs = []
        x = 0.0
        for ch in s:
            f = char_font(ch, cn_font, en_font)
            if runs and runs[-1][0] is f:
                runs[-1][1] += ch
                runs[-1][2].append(x)
            else:
                runs.append([f, ch, [x]])
            x += f.getlength(ch) + sp
        return [(f, seg, pos) for f, seg, pos in runs]

    def split_lines(text):
        """只在输入框手动换行处断行（不再按字数自动截断）。"""
        return text.split('\n')

    def _tokens(ln):
        """把一行切成「整体不拆」的块 + 单个字符。

        需要整体保留的（换行时不能从中间劈开）：
        - `#`/`@`/`$` 后面跟一串字母数字，如 `#1234567`、`@abc`
        - 纯数字串，如 `1234567`
        其余一律按单字切，方便标点禁则和逐字折行。
        """
        toks, i, n = [], 0, len(ln)
        while i < n:
            ch = ln[i]
            if ch in '#@$':
                j = i + 1
                while j < n and (ln[j].isalnum() or ln[j] in '_-'):
                    j += 1
                if j > i + 1:                      # 标记符后面有内容才算整体
                    toks.append(ln[i:j])
                    i = j
                    continue
            if ch.isdigit():
                j = i
                while j < n and (ln[j].isdigit() or ln[j] in '.,:'):
                    j += 1
                toks.append(ln[i:j])
                i = j
                continue
            toks.append(ch)
            i += 1
        return toks

    def wrap_to_width(lines, twidth, max_w):
        """把每行按宽度上限折行。

        规则：
        - `#1234567` / 纯数字这类「原子串」整体不拆（除非它自己就超宽）
        - 英文单词尽量不从中间劈开：回退到最后一个空格
        - 标点禁则：「不置行首」的标点跟前一字一起带到下行；「不置行末」的推到下行
        twidth(s) 是「按中英混排规则算整段宽度」的函数。
        """
        out = []
        for ln in lines:
            if not ln or twidth(ln) <= max_w:
                out.append(ln)
                continue
            # 原子串自己就超宽 -> 只能退化成一个字一个字地拆
            toks = []
            for t in _tokens(ln):
                toks.extend(list(t) if (len(t) > 1 and twidth(t) > max_w) else [t])

            cur = ''
            for tok in toks:
                if not cur or twidth(cur + tok) <= max_w:
                    cur += tok
                    continue
                # 放不下 -> 先把 cur 收尾，tok 留到下一行
                # 标点禁则：不能在行首的标点，跟前一个字符一起挪到下一行
                if tok[0] in PROMO_NO_LINE_START and len(cur) > 1:
                    cur, carry = cur[:-1], cur[-1]
                    out.append(cur)
                    cur = carry + tok
                    continue
                # 不能在行末的标点（开括号/前引号），推到下一行
                if cur[-1] in PROMO_NO_LINE_END:
                    cur, carry = cur[:-1], cur[-1]
                    out.append(cur)
                    cur = carry + tok
                    continue
                # 英文单词尽量不从中间劈开：回退到最后一个空格
                if ' ' in cur and not cur.endswith(' '):
                    head, _, tail = cur.rpartition(' ')
                    if head:
                        out.append(head)
                        cur = tail + tok
                        continue
                out.append(cur)
                cur = tok
            out.append(cur)
        return out

    def build(img, text, align):
        if ios:
            # iOS 的点九参数由规格手动指定（不从黑线读）：
            #   拉伸区 = 纵向第 PROMO_IOS_STRETCH_Y 那 1px、横向第 PROMO_IOS_STRETCH_X 那 1px
            #   （坐标是「1-based 第几格」，换算内部 0-based 索引要 -1）
            # 注意：load_9 已经替 iOS 去掉了那 1px 黑边，这里拿到的就是内部图，
            # 尺寸直接用 img.width / img.height，**不能再减 2**（减两次会错位变形）
            iw, ih = img.width, img.height
            # 横向拉伸区按左右镜像取：右气泡「左往右第106格」/ 左气泡「右往左第106格」
            # 规格给的是**带 1px 黑边的文件**上的 1-based 格号：
            #   文件坐标 → 内部 0-based = 格号 − 2（−1 转 0-based、−1 去掉那圈边框）
            sx_col = PROMO_IOS_STRETCH_X if align == 'right' else PROMO_IOS_L_STRETCH_X
            sx0 = sx_col - 2
            sy0 = PROMO_IOS_STRETCH_Y - 2
            np_params = {
                'stretch_x': (sx0, sx0 + 1), 'stretch_y': (sy0, sy0 + 1),
                'fixed_left': sx0, 'fixed_right': iw - (sx0 + 1),
                'fixed_top': sy0, 'fixed_bottom': ih - (sy0 + 1),
                'pad_left': 0, 'pad_right': 0, 'pad_top': 0, 'pad_bottom': 0,
                'internal_w': iw, 'internal_h': ih,
            }
        else:
            np_params = parse_nine_patch(img)
            iw, ih = np_params['internal_w'], np_params['internal_h']

        pl, pr = np_params['pad_left'], np_params['pad_right']
        pt, pb = np_params['pad_top'], np_params['pad_bottom']
        # 最小尺寸 = 素材点九图本身大小（单字时也不压缩，保持原始图尺寸）
        min_w = max(np_params['fixed_left'] + np_params['fixed_right'], img.width)
        min_h = max(np_params['fixed_top'] + np_params['fixed_bottom'], img.height)

        # ── 留白基准框（左缘/右缘/上缘/下缘，内部坐标）────────────────
        # 安卓：点九黑线框（底边黑线给横向 bb_l/bb_r、右边黑线给纵向 bb_t/bb_b）
        # IOS：没有黑线，改用气泡实体（不透明像素）bbox
        if ios:
            # iOS 的文字区按规格给绝对坐标（内部 0-based）：
            #   右气泡：左起 75、右止 宽−45；左气泡镜像 → 左起 45、右止 宽−75
            #   上起 63、下止 高−68（上下不镜像）
            bb_l, bb_r, bb_t, bb_b = 0, iw, 0, ih
            if align == 'right':
                ins_l, ins_r = PROMO_IOS_TEXT_L, PROMO_IOS_TEXT_R
            else:
                ins_l, ins_r = PROMO_IOS_TEXT_R, PROMO_IOS_TEXT_L
            ins_t, ins_b = PROMO_IOS_TEXT_T, PROMO_IOS_TEXT_B
            edge_l, edge_r = ins_l, ins_r
            edge_t = ins_t
        else:
            bb_l = np_params['pad_left']
            bb_r = iw - np_params['pad_right']
            bb_t = np_params['pad_top']
            bb_b = ih - np_params['pad_bottom']
            if align == 'right':
                ins_l, ins_r, ins_t, ins_b = (PROMO_INSET_L, PROMO_INSET_R,
                                              PROMO_INSET_T, PROMO_INSET_B)
            else:
                ins_l, ins_r, ins_t, ins_b = (PROMO_L_INSET_L, PROMO_L_INSET_R,
                                              PROMO_L_INSET_T, PROMO_L_INSET_B)
            edge_l = bb_l + ins_l
            edge_r = (iw - bb_r) + ins_r
            edge_t = bb_t + ins_t

        def edges(gl, gr):
            """(左缘, 右缘) 距气泡边缘的距离（安卓用；iOS 已直接算好）。"""
            return bb_l + gl, (iw - bb_r) + gr

        lines = split_lines(text) if text else []
        if ios:
            # iOS 中英文统一用苹方，字号独立（没传字号时用 iOS 自己的默认值）
            f = _load_font(PROMO_IOS_FONT, font_size or PROMO_IOS_FONT_SIZE)
            cn_font = en_font = f
        else:
            cn_font, en_font = load_font(font_size or PROMO_FONT_SIZE)

        if lines:
            # 混排行高取两种字体里大的，再乘系数收窄行距（避免重叠的同时压紧一点）
            a1, d1 = cn_font.getmetrics()
            a2, d2 = en_font.getmetrics()
            line_h = max(a1 + d1, a2 + d2) * PROMO_LINE_H_RATIO
            ascent = max(a1, a2)
        else:
            ascent = line_h = 0.0

        def twidth(s):
            return text_width(s, cn_font, en_font)

        wrapped = False
        if ios:
            # iOS：文字区固定（规格给死），不分档、不退让
            max_w = PROMO_IOS_MAX_W
            edge_b = ins_b
            avail = max_w - edge_l - edge_r
            if lines:
                if avail > 0:
                    wrapped = len(wrap_to_width(lines, twidth, avail)) > len(lines)
                    lines = wrap_to_width(lines, twidth, avail)
                widths = [twidth(ln) for ln in lines]
                text_w = max(widths)
            else:
                widths = []
                text_w = 0.0
        else:
            # 安卓：左侧（主侧）留白分档 —— 文字宽超阈值算「横向拉伸」
            stretched = bool(lines) and max(twidth(ln) for ln in lines) > PROMO_STRETCH_TEXT_W
            pair = (PROMO_INSET_L, PROMO_INSET_L_STRETCH, PROMO_INSET_R,
                    PROMO_INSET_R_WRAP, PROMO_INSET_B, PROMO_INSET_B_WRAP)
            pair_l = (PROMO_L_INSET_L, PROMO_L_INSET_L_STRETCH, PROMO_L_INSET_R,
                      PROMO_L_INSET_R_WRAP, PROMO_L_INSET_B, PROMO_L_INSET_B_WRAP)
            base_l, str_l, base_r, wrap_r, base_b, wrap_b = \
                pair if align == 'right' else pair_l
            ins_l = str_l if stretched else base_l
            max_w = PROMO_MAX_BUBBLE_W
            edge_l = bb_l + ins_l
            if lines:
                # 先用「不换行档」右留白：放得下就用它；放不下退让到「换行档」再试
                for cur_r in (base_r, wrap_r):
                    ins_r = cur_r
                    edge_r = (iw - bb_r) + ins_r
                    avail = max_w - edge_l - edge_r
                    if avail <= 0:
                        continue
                    if len(wrap_to_width(lines, twidth, avail)) <= len(lines):
                        break               # 这一档放得下
                else:
                    wrapped = True          # 两档都放不下 -> 真折行
                ins_r = base_r if not wrapped else ins_r
                edge_r = (iw - bb_r) + ins_r
                avail = max_w - edge_l - edge_r
                if avail > 0:
                    lines = wrap_to_width(lines, twidth, avail)
                widths = [twidth(ln) for ln in lines]
                text_w = max(widths)
            else:
                edge_r = (iw - bb_r) + ins_r
                widths = []
                text_w = 0.0
            # 下留白分档：不换行用基准值，换行用换行档
            edge_b = (ih - bb_b) + (wrap_b if wrapped else base_b)

        text_h = line_h * len(lines)

        # iOS 按「字形」而不是「行盒」对齐：
        #   - 顶部：把第一行字形距行盒顶的空隙 ink_top 抵消掉 -> 字形顶正好落 edge_t
        #   - 底部（含换行）：高度锚定「最后一行的字形底」，让
        #     最后一行墨迹底 -> 气泡底 正好等于 edge_b（规格 70px）
        ink_top = ink_bot_ink = 0
        if ios and lines:
            boxes = [cn_font.getbbox(ln) for ln in lines if ln]
            boxes = [b for b in boxes if b]
            if boxes:
                ink_top = min(b[1] for b in boxes)      # 字形顶距行盒顶
                ink_bot_ink = max(b[3] for b in boxes)  # 字形底距行盒顶
        if ios and lines:
            # 末行基线 = edge_t + (n-1)*line_h + ascent - ink_top
            # 末行墨迹底 = 基线 + (ink_bot_ink - ascent)
            last_ink_bottom = (edge_t + (len(lines) - 1) * line_h
                               - ink_top + ink_bot_ink)
            # last_ink_bottom 已是「含 edge_t 的绝对 y」，所以高度只要再补 edge_b
            content_bottom = last_ink_bottom + edge_b
        else:
            content_bottom = text_h + edge_t + edge_b

        # 触发折行时，气泡总宽直接拉到上限
        target_w = max_w if wrapped \
            else max(min_w, math.ceil(text_w + edge_l + edge_r))
        target_h = max(min_h, math.ceil(content_bottom))
        bubble = nine_patch_scale(img, target_w, target_h, np_params)
        if lines:
            draw = ImageDraw.Draw(bubble)
            # iOS 且气泡没被拉伸（宽度还停在素材原宽）时，文字在内容区**水平居中**；
            # 一旦被拉宽（含折行拉满），回到左对齐
            center_zone = (ios and not wrapped
                           and target_w <= min_w)
            zone_w = target_w - edge_l - edge_r
            for i, ln in enumerate(lines):
                # 基线 = 上留白 + 已累计行高 + 本行 ascent（iOS 再抬掉字形上空隙）
                base_y = edge_t + i * line_h + ascent - ink_top
                x0 = edge_l
                if center_zone:
                    x0 = edge_l + (zone_w - twidth(ln)) / 2.0   # 每行各自居中
                # 逐字符渲染：中文 / 英文各用各的字体，按字宽+字间距逐个定位
                for f, seg, xs in split_runs(ln, cn_font, en_font):
                    for ch, dx in zip(seg, xs):
                        draw.text((x0 + dx, base_y), ch, font=f,
                                  fill=text_color + (255,), anchor="ls")
        return bubble

    # 安卓 / IOS 读同一份素材（176×176 带 1px 黑边）；iOS 在 load_9 里自动去边框
    left = build(load_9('left_.9.png'), left_text, 'left')
    right = build(load_9('right_.9.png'), right_text, 'right')
    return {"左侧气泡": left, "右侧气泡": right}


PROMO_TEXT_INSET_X = 14  # 已废弃：气泡宣传改为严格按点九 padding，保留仅为兼容旧引用
PROMO_TEXT_INSET_Y = 8   # 已废弃：同上

# 气泡宣传字体：中文 = 微软雅黑 Light，英文/数字/半角符号 = Segoe UI
# 按候选顺序取第一个可用的，保证 mac 打包后也有兜底
PROMO_FONT_CN = [os.path.join(WORK_DIR, 'fonts', 'NotoSansSC-Light.ttf'),  # 开源 OFL
                 'C:/Windows/Fonts/msyhl.ttc',       # 回退：Windows 微软雅黑 Light
                 os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf')]
PROMO_FONT_EN = [os.path.join(WORK_DIR, 'fonts', 'NotoSans-Light.ttf'),  # 开源 OFL（与中文同族）
                 os.path.join(WORK_DIR, 'fonts', 'Roboto-Regular.ttf'),
                 'C:/Windows/Fonts/segoeui.ttf',     # 回退：Windows Segoe UI
                 os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf')]
# 安卓那套的默认字号（iOS 用 PROMO_IOS_FONT_SIZE）
PROMO_FONT_SIZE = 50

# 气泡宣传的留白（绝对 px）——单行/多行统一，且从「点九黑线框」往里量：
#   黑线框 = 底边黑线给横向、右边黑线给纵向围出的区域（等于 parse_nine_patch 的 pad 框）
#   右气泡：左 45|30 / 右 45 / 上 22 / 下 25(不换行 28)。左气泡另一套独立值（见下），不镜像
PROMO_INSET_L = 45           # 右气泡左留白·不拉伸时
PROMO_INSET_L_STRETCH = 30   # 右气泡左留白·横向拉伸时
PROMO_INSET_R = 45           # 右气泡右留白·不换行
PROMO_INSET_R_WRAP = 25      # 右气泡右留白·换行时
# 横向拉伸判据：文字宽超过这个值就算拉伸（按「一个文字时下点九黑线的中间空余」量的）
PROMO_STRETCH_TEXT_W = 65
# 字间距（px）：每个字符后额外留的空白，0 = 不加
PROMO_LETTER_SPACING = 1
# 行距系数：行高 = 字体自然行高(ascent+descent) × 该系数（1.0 = 原样，<1 更紧凑）
PROMO_LINE_H_RATIO = 0.9014
# 折行上限 = 整个气泡的总宽度（含 1px 点九黑边）。文字撑过就自动折行，
# 折行时气泡直接拉到该总宽。
PROMO_MAX_BUBBLE_W = 776


# 折行标点禁则（中文排版惯例）
# 不能出现在行首的标点：若折行会把它顶到下一行行首，就把前一个字符一起带下去
PROMO_NO_LINE_START = set('，。、；：？！）】》」』”’…—·,.;:?!)]}>')
# 不能出现在行末的标点：开括号 / 前引号，折行时推到下一行
PROMO_NO_LINE_END = set('（【《「『“‘([{<')
PROMO_INSET_T = 22   # 右气泡上留白
PROMO_INSET_B = 28   # 右气泡下留白·不换行
PROMO_INSET_B_WRAP = 32   # 右气泡下留白·换行时

# 左气泡另一套独立留白——同样从黑线框往里量
PROMO_L_INSET_L = 63           # 左气泡左留白·不拉伸时
PROMO_L_INSET_L_STRETCH = 43   # 左气泡左留白·横向拉伸时
PROMO_L_INSET_R = 35   # 左气泡右留白·不换行
PROMO_L_INSET_R_WRAP = 25    # 左气泡右留白·换行时
PROMO_L_INSET_T = 22   # 左气泡上留白
PROMO_L_INSET_B = 28   # 左气泡下留白·不换行
PROMO_L_INSET_B_WRAP = 32   # 左气泡下留白·换行时

# ── IOS 那套（176×176 带 1px 黑边素材，点九参数按规格手写）───────────
# 拉伸区（1-based 格号）：
#   纵向：上往下第 82 格那 1px（左右气泡相同）
#   横向：右气泡「左往右第 106 格」；左气泡镜像 ——「右往左第 106 格」
#         镜像索引 = 内部宽 174 − 106 = 68（1-based）→ 见 build 里的换算
PROMO_IOS_STRETCH_Y = 82
PROMO_IOS_STRETCH_X = 106           # 右气泡：左往右第 106 格
PROMO_IOS_L_STRETCH_X = 71          # 左气泡：右往左第 106 格（含边框镜像 = 176−106+1）
# 文字区（内部 0-based 绝对坐标换算的留白）
#   左起第 75px、右止 宽−45；上起 63px、下止 高−68
PROMO_IOS_TEXT_L = 75
PROMO_IOS_TEXT_R = 45
PROMO_IOS_TEXT_T = 63
PROMO_IOS_TEXT_B = 68
# 最宽（含 1px 黑边）
PROMO_IOS_MAX_W = 905
# iOS 独立的字间距（安卓用 PROMO_LETTER_SPACING=1，iOS 不加字距）
PROMO_IOS_LETTER_SPACING = 0
# iOS 独立字体（中文/英文都用苹方）与默认字号
PROMO_IOS_FONT = [os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf'),
                  'C:/Windows/Fonts/msyh.ttc']
PROMO_IOS_FONT_SIZE = 50

# ── 气泡预览图（470×470 画板）─────────────────────────────────────
BUBBLE_PREVIEW_SIZE = 470          # 画板边长
BUBBLE_PREVIEW_BASE = 168          # 气泡起始尺寸（短文案就是这个大小）
BUBBLE_PREVIEW_LEFT_XY = (72, 90)  # 左气泡左上角
BUBBLE_PREVIEW_RIGHT_XY = (392, 230)   # 右气泡右上角
BUBBLE_PREVIEW_FONT_SIZE = 38      # 默认字号
BUBBLE_PREVIEW_BG_NAME = '气泡预览图背景.png'   # 可上传替换
# 左右气泡各自的最大可用宽度（画板内）
BUBBLE_PREVIEW_MAX_W_LEFT = BUBBLE_PREVIEW_SIZE - BUBBLE_PREVIEW_LEFT_XY[0]
BUBBLE_PREVIEW_MAX_W_RIGHT = BUBBLE_PREVIEW_RIGHT_XY[0]


def _generate_bubble_preview(left_text='', right_text='', font_size=None,
                             text_color=(51, 51, 51)):
    """气泡预览图：470×470 画板上摆左右两颗气泡。

    - 背景：用户上传的 `气泡预览图背景.png`（USER_DATA_DIR），没有就纯白
    - 气泡素材沿用气泡宣传那套 `left_.9.png` / `right_.9.png`
    - 先把素材（内部 174×174）等比缩到 **168×168** 作为起始尺寸，
      点九参数与留白同比缩放（k = 168/174）
    - 左气泡**左上角**(72,90)、**向右延长**；右气泡**右上角**(392,230)、**向左延长**
    - 文字左右分开输入，苹方，默认字号 47
    返回 470×470 的 RGBA 图。
    """
    from PIL import ImageDraw, ImageFont

    size = font_size or BUBBLE_PREVIEW_FONT_SIZE
    CANVAS = BUBBLE_PREVIEW_SIZE
    BASE = BUBBLE_PREVIEW_BASE

    # ── 背景 ──
    bg_path = os.path.join(USER_DATA_DIR, BUBBLE_PREVIEW_BG_NAME)
    if os.path.exists(bg_path):
        canvas = Image.open(bg_path).convert('RGBA')
        if canvas.size != (CANVAS, CANVAS):
            canvas = canvas.resize((CANVAS, CANVAS), Image.LANCZOS)
    else:
        canvas = Image.new('RGBA', (CANVAS, CANVAS), (255, 255, 255, 255))

    # ── 字体 ──
    def load_font(sz):
        for fp in [os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf'),
                   'C:/Windows/Fonts/msyh.ttc']:
            try:
                return ImageFont.truetype(fp, sz)
            except Exception:
                continue
        return ImageFont.load_default()
    font = load_font(size)

    def prepare(fn, align):
        """载入素材 → 去 1px 边框 → 缩到 BASE → 点九参数按 iOS 规格缩放。"""
        p = os.path.join(USER_DATA_DIR, fn)
        if not os.path.exists(p):
            p = os.path.join(WORK_DIR, fn)
        im = Image.open(p).convert('RGBA')
        inner = im.crop((1, 1, im.width - 1, im.height - 1))   # 去 1px 黑边
        k = BASE / float(inner.width)                          # 缩到 168 的系数
        inner = inner.resize((BASE, BASE), Image.LANCZOS)
        # 拉伸区按 **iOS 规格**（文件 1-based 格号 → 内部 0-based 要 −2），再按 k 缩
        sx_col = PROMO_IOS_STRETCH_X if align == 'right' else PROMO_IOS_L_STRETCH_X
        sx0 = int(round((sx_col - 2) * k))
        sy0 = int(round((PROMO_IOS_STRETCH_Y - 2) * k))
        n2 = {
            'internal_w': BASE, 'internal_h': BASE,
            'stretch_x': (sx0, sx0 + 1), 'stretch_y': (sy0, sy0 + 1),
            'fixed_left': sx0, 'fixed_right': BASE - (sx0 + 1),
            'fixed_top': sy0, 'fixed_bottom': BASE - (sy0 + 1),
            'pad_left': 0, 'pad_right': 0, 'pad_top': 0, 'pad_bottom': 0,
        }
        return inner, n2

    # ── 左右两侧的素材与文字留白（用 iOS 那套，按 k 缩；左气泡左右镜像）──
    def side(align):
        if align == 'left':
            img, np_ = prepare('left_.9.png', 'left')
            L, R = PROMO_IOS_TEXT_R, PROMO_IOS_TEXT_L
        else:
            img, np_ = prepare('right_.9.png', 'right')
            L, R = PROMO_IOS_TEXT_L, PROMO_IOS_TEXT_R
        k = BASE / 174.0
        return img, np_, L * k, R * k, PROMO_IOS_TEXT_T * k, PROMO_IOS_TEXT_B * k

    def wrap(text, maxw, cn_font):
        """按宽度折行（中文逐字、英文尽量按空格）。"""
        out = []
        for ln in (text.split('\n') if text else []):
            if not ln or cn_font.getlength(ln) <= maxw:
                out.append(ln)
                continue
            cur = ''
            for ch in ln:
                if cur and cn_font.getlength(cur + ch) > maxw:
                    if ch != ' ' and ' ' in cur:
                        head, _, tail = cur.rpartition(' ')
                        if head:
                            out.append(head)
                            cur = tail + ch
                            continue
                    out.append(cur)
                    cur = ch
                else:
                    cur += ch
            out.append(cur)
        return out

    def build(align, text, max_w):
        img, np_, edge_l, edge_r, edge_t, edge_b = side(align)

        # 折行宽度 = 画板可用宽度 − 左右留白
        lines = wrap(text, max(60, max_w - edge_l - edge_r), font)
        if lines:
            a, d = font.getmetrics()
            line_h = a + d
        else:
            a = line_h = 0
        widths = [font.getlength(l) for l in lines]
        text_w = max(widths) if widths else 0

        # iOS 那套：按【字形】对齐 —— 抬掉字形距行盒顶的空隙，
        # 高度锚定末行字形底 + edge_b（换行后"最后一笔到气泡底"恒为 edge_b）
        ink_top = ink_bot_ink = 0
        if lines:
            boxes = [font.getbbox(l) for l in lines if l]
            boxes = [b for b in boxes if b]
            if boxes:
                ink_top = min(b[1] for b in boxes)
                ink_bot_ink = max(b[3] for b in boxes)
        if lines:
            content_bottom = (edge_t + (len(lines) - 1) * line_h
                              - ink_top + ink_bot_ink + edge_b)
        else:
            content_bottom = edge_t + edge_b

        target_w = max(BASE, int(math.ceil(text_w + edge_l + edge_r)))
        target_h = max(BASE, int(math.ceil(content_bottom)))
        bubble = nine_patch_scale(img, target_w, target_h, np_)

        if lines:
            draw = ImageDraw.Draw(bubble)
            # 竖直居中：算文字块【字形】的实占高度，在气泡里上下均分
            ink_h = (len(lines) - 1) * line_h + ink_bot_ink - ink_top
            block_top = (target_h - ink_h) / 2.0 - ink_top
            for i, ln in enumerate(lines):
                base_y = block_top + i * line_h + a
                draw.text((edge_l, base_y), ln, font=font,
                          fill=text_color + (255,), anchor="ls")
        return bubble

    left = build('left', left_text, BUBBLE_PREVIEW_MAX_W_LEFT)
    right = build('right', right_text, BUBBLE_PREVIEW_MAX_W_RIGHT)

    # ── 摆到画板上 ──
    lx, ly = BUBBLE_PREVIEW_LEFT_XY                 # 左气泡左上角，向右延长
    rx, ry = BUBBLE_PREVIEW_RIGHT_XY                # 右气泡右上角，向左延长
    canvas.alpha_composite(left, (lx, ly))
    canvas.alpha_composite(right, (rx - right.width, ry))
    return canvas


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
    # 无字导出图保持原样：整颗气泡 420×174
    shop = nine_patch_scale(left_9, 420, 174, np_left)
    shop_with_text = shop
    if shop_text_img is not None:
        # (预览) 版：气泡先按点九包住 6 字 → 再以文字中心为轴横着拉伸填满 420 宽
        glyph = shop_text_img.getbbox()
        if glyph:
            gl, gt, gr, gb = glyph
            gw, gh = gr - gl, gb - gt
            pt = np_left['pad_top']
            pb = np_left['pad_bottom']
            bub_h = max(pt + gh + pb,
                        np_left['fixed_top'] + np_left['fixed_bottom'])
            bub = nine_patch_scale(left_9, 420, bub_h, np_left)   # 宽=满幅420
            # 粉框(内容区)在气泡内的映射位置 → 文字中心对准粉框中心
            bx0, by0, bx1, by1 = map_rect_np(np_left, PINK_LEFT_BOX, 420, bub_h)
            ccx = (bx0 + bx1) / 2.0
            ccy = (by0 + by1) / 2.0
            glyph_img = shop_text_img.crop(glyph)
            bub.paste(glyph_img,
                      (round(ccx - gw / 2.0), round(ccy - gh / 2.0)), glyph_img)
            # 用 alpha_composite 而不是 paste：贴到全透明画布上时，paste 会把
            # 半透明像素按 alpha 与目标(全黑)加权，导致气泡边缘发黑
            cw = Image.new('RGBA', (420, 174), (0, 0, 0, 0))
            cw.alpha_composite(bub, (0, round((174 - bub_h) / 2.0)))   # 纵向居中
            shop_with_text = cw

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

            # 生成气泡
            bubble = nine_patch_scale(left_9, bubble_w, bubble_h, np_left)

            # 红框（内容区）在气泡内的映射位置（按 04 参考粉框 PINK_LEFT_BOX）
            bx0, by0, bx1, by1 = map_rect_np(np_left, PINK_LEFT_BOX, bubble_w, bubble_h)
            ccx = (bx0 + bx1) / 2.0
            ccy = (by0 + by1) / 2.0

            # wz_3 文字中心放在内容框中心
            text_x = round(ccx - tw / 2.0)
            text_y = round(ccy - th / 2.0)
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

            # 摆气泡使内容框中心对准画布中心 (183,102)，不再按气泡外框居中
            bx = round(183 - ccx)
            by = round(102 - ccy)
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
    if text_color_dark is None:
        text_color_dark = TEXT_COLOR_DARK
        tag_color_dark = TAG_COLOR_DARK
        tag_bg_color_dark = TAG_BG_COLOR_DARK
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
    # 带文字的预览图，放输出根目录（zip 最外层，与 封面/效果 等文件夹同级）
    imgs["商城6字展示420X174(预览)"].save(
        os.path.join(OUTPUT_DIR, '商城6字展示420X174(预览).png'))
    print("  → 商城6字展示420X174(预览).png")
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
        # 亮色 + 暗色 6 个色值全部替换（暗色模板色：#7ea6d2/#afb0bf/#546c94）
        replacements = [
            ('#6985c5', rgb_to_hex(text_color)),
            ('#97979e', rgb_to_hex(tag_color)),
            ('#d1e2fe', rgb_to_hex(tag_bg_color)),
            ('#7ea6d2', rgb_to_hex(text_color_dark)),
            ('#afb0bf', rgb_to_hex(tag_color_dark)),
            ('#546c94', rgb_to_hex(tag_bg_color_dark)),
        ]
        # 先换成占位符再回填，避免替换出的新色值恰好等于另一个待替换旧色值时被二次替换
        for i, (old, _) in enumerate(replacements):
            xml = xml.replace(old, f'__COLOR_PH_{i}__')
        for i, (_, new) in enumerate(replacements):
            xml = xml.replace(f'__COLOR_PH_{i}__', new)
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


# ═══ 阶段二：主页皮肤.gif / 被赞动效.gif 动效合成 ═══════════════════

def _ffmpeg_bin():
    """定位 ffmpeg/ffprobe：(打包bundle内 sys._MEIPASS / exe同目录) → 脚本同目录 → PATH。

    打包时需把 ffmpeg.exe/ffprobe.exe 用 --add-data/--add-binary 打进 bundle。
    """
    import sys, os, shutil
    is_win = os.name == 'nt'
    ff, fp = ('ffmpeg.exe', 'ffprobe.exe') if is_win else ('ffmpeg', 'ffprobe')
    bases = []
    if getattr(sys, 'frozen', False):
        bases += [getattr(sys, '_MEIPASS', ''), os.path.dirname(sys.executable)]
    bases.append(os.path.dirname(os.path.abspath(__file__)))
    for b in bases:
        if not b:
            continue
        p1, p2 = os.path.join(b, ff), os.path.join(b, fp)
        if os.path.exists(p1) and os.path.exists(p2):
            return p1, p2
    return shutil.which('ffmpeg'), shutil.which('ffprobe')


def _swflags():
    """Windows 打包版(无控制台)调 ffmpeg/ffprobe 时禁止弹控制台窗口。"""
    import os
    return 0x08000000 if os.name == 'nt' else 0   # CREATE_NO_WINDOW


def load_gif_abs(path):
    """逐帧解码 gif → (绝对帧 RGBA 列表, 每帧毫秒列表)。

    处理 disposal：透明处让位给上一帧内容，导出每帧的完整画面。
    """
    im = Image.open(path)
    n = getattr(im, 'n_frames', 1)
    frames, durs = [], []
    prev = None
    for i in range(n):
        im.seek(i)
        dur = int(im.info.get('duration', 0) or 100)
        disp = int(getattr(im, 'disposal_method', 0) or 0)
        fr = im.convert('RGBA')
        if prev is None or disp == 2:      # dispose 到背景：从透明底开始
            canvas = fr
        elif disp == 3:                    # 恢复到上一帧前
            canvas = prev.copy()
            canvas.alpha_composite(fr)
        else:                              # 不清除：叠加到上一帧
            canvas = prev.copy()
            canvas.alpha_composite(fr)
        frames.append(canvas)
        durs.append(dur)
        prev = canvas
    return frames, durs


def read_mp4_frames(path, max_frames=0):
    """用 ffmpeg/ffprobe 解 mp4 → (RGBA 帧列表, fps)。（不再依赖 cv2，便于打包）"""
    import json, subprocess
    ff, fp = _ffmpeg_bin()
    if not ff or not fp:
        raise RuntimeError("未找到 ffmpeg/ffprobe，无法解码 mp4")
    # 探测宽高与帧率
    prob = subprocess.run(
        [fp, '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', path],
        capture_output=True, text=True, creationflags=_swflags())
    try:
        info = json.loads(prob.stdout)['streams'][0]
        w, h = int(info['width']), int(info['height'])
        n, d = info.get('r_frame_rate', '24/1').split('/')
        fps = float(n) / float(d) if float(d) else 24.0
    except Exception:
        return [], 24.0
    if fps <= 0:
        fps = 24.0

    import numpy as np
    cmd = [ff, '-v', 'error', '-i', path]
    if max_frames:
        cmd += ['-frames:v', str(max_frames)]
    cmd += ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=_swflags())
    frame_size = w * h * 3
    frames = []
    try:
        while proc.stdout:
            buf = bytearray(frame_size)
            got = 0
            while got < frame_size:
                chunk = proc.stdout.read(frame_size - got)
                if not chunk:
                    break
                buf[got:got + len(chunk)] = chunk
                got += len(chunk)
            if got < frame_size:
                break
            arr = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, 3).copy()
            frames.append(Image.fromarray(arr, 'RGB').convert('RGBA'))
            if max_frames and len(frames) >= max_frames:
                break
    finally:
        proc.terminate()
    return frames, fps


def _like_alpha(i, n):
    """点赞胶囊+文字的显隐系数 0..1。

    出现：参考第1帧 0%、第4帧→100%；之后保持 100% 直到最后一帧，
    与点赞gif内容在循环点一起消失（避免框比gif早走一帧）。
    参考总帧=19 等比换算到实际帧数 n。
    """
    if n <= 0:
        return 0.0
    p = (i + 1) * 19.0 / n          # 把 (i+1) 投到参考坐标系 1..19
    if p <= 1:
        return 0.0
    if p <= 4:
        return (p - 1) / 3.0
    return 1.0


def _gradient_rect(left, right, w=206, h=84):
    """纯左右渐变(左→右)的长方形图 RGBA（=导出的 db#xxx.png 本体）。"""
    import numpy as np
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for x in range(w):
        t = x / (w - 1)
        arr[:, x, 0] = int(left[0] + (right[0] - left[0]) * t)
        arr[:, x, 1] = int(left[1] + (right[1] - left[1]) * t)
        arr[:, x, 2] = int(left[2] + (right[2] - left[2]) * t)
    arr[:, :, 3] = 255
    return Image.fromarray(arr, 'RGBA')


def _capsule_img(src_dir, left, right, w=206, h=84):
    """左右渐变用 胶囊.png(拉伸到同尺寸) 当蒙版 → 胶囊成品 RGBA（gif 内使用）。

    默认 206×84；页上胶囊传胶囊.png 原生尺寸(479×84)。
    """
    grad = _gradient_rect(left, right, w, h)
    mask = Image.open(os.path.join(src_dir, '胶囊.png')).convert('RGBA')
    mask = mask.resize((w, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def _load_like_text(src_dir, color):
    """点赞文字.png（改颜色的/ 优先）染成 点赞文字色。"""
    for p in [os.path.join(src_dir, '改颜色的', '点赞文字.png'),
              os.path.join(src_dir, '点赞文字.png')]:
        if os.path.isfile(p):
            return color_replace_simple(Image.open(p).convert('RGBA'), color)
    return None


def _ffmpeg_gif(frames, durs_ms, colors=256, dither='sierra2_4a'):
    """用 ffmpeg palettegen/paletteuse 编码 GIF（保色更好，参考动态壁纸项目）。

    逐帧写 PNG → concat 带各自时长 → 全局调色板 + 抖动。无 ffmpeg 返回 None（回退 PIL）。
    """
    import os, subprocess, tempfile
    ff, _ = _ffmpeg_bin()
    if not ff or not frames:
        return None
    with tempfile.TemporaryDirectory() as td:
        paths, lines = [], []
        for i, fr in enumerate(frames):
            p = f'f{i:04d}.png'
            fr.convert('RGB').save(os.path.join(td, p), compress_level=0, optimize=False)
            paths.append(p)
            sec = max(0.02, durs_ms[i] / 1000.0)
            lines.append(f"file '{p}'")
            lines.append(f"duration {sec:.3f}")
        lines.append(f"file '{paths[-1]}'")   # gif 末帧重复占位
        with open(os.path.join(td, 'list.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines) + '\n')
        out = os.path.join(td, 'out.gif')
        vf = (f"[0:v]split[s0][s1];[s0]palettegen=max_colors={colors}[p];"
              f"[s1][p]paletteuse=dither={dither}")
        r = subprocess.run(
            [ff, '-y', '-f', 'concat', '-safe', '0', '-i', 'list.txt',
             '-filter_complex', vf, '-loop', '0', 'out.gif'],
            capture_output=True, text=True, cwd=td, creationflags=_swflags())
        if r.returncode != 0 or not os.path.exists(out):
            return None
        with open(out, 'rb') as fh:
            return fh.read()


def _save_gif_bytes(frames, durs_ms, max_bytes=GIF_MAX_BYTES, shared_palette=False):
    """编码 GIF bytes。优先 ffmpeg 全局调色板保色；无 ffmpeg 回退 PIL。

    预览(shared_palette=True)：bayer 抖动更快更小；导出：sierra2_4a 更贴源片色。
    超过 max_bytes：逐级“降色 + 抽帧减半”，直到压进阈值。
    """
    import io

    def halve(fs, ds):
        f2 = fs[::2]
        d2 = []
        for j in range(0, len(ds), 2):
            d2.append(max(1, int(round(sum(ds[j:j + 2])))))
        return f2, d2[:len(f2)]

    if frames:
        dither = 'bayer:bayer_scale=2' if shared_palette else 'sierra2_4a'
        last = None
        fs, ds = frames, durs_ms
        # 计划：0/1 全帧降色 → 之后逐步抽帧减半 + 继续降色
        plan = [(256, 0), (160, 0), (128, 1), (96, 1), (80, 2), (64, 2), (48, 3)]
        if shared_palette:
            plan = [(128, 0), (96, 0), (80, 1), (64, 1), (48, 2)]
        for colors, halves in plan:
            for _ in range(halves):
                if len(fs) <= 1:
                    break
                fs, ds = halve(fs, ds)
            if not fs:
                break
            data = _ffmpeg_gif(fs, ds, colors=colors, dither=dither)
            if data is None:
                break  # 无 ffmpeg → 走 PIL 回退
            last = data
            if len(data) <= max_bytes:
                return data
        if last is not None:
            return last  # 已尽量压

    def enc(colors, shared):
        buf = io.BytesIO()
        if shared:
            src_idx = len(frames) // 2
            pal = frames[src_idx].convert('RGB').quantize(
                colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
            first = frames[0].convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE)
            rest = [f.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE)
                    for f in frames[1:]] if len(frames) > 1 else []
        else:
            q = lambda im: im.convert('RGB').quantize(
                colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
            first = q(frames[0])
            rest = [q(f) for f in frames[1:]] if len(frames) > 1 else []
        first.save(buf, format='GIF', save_all=True, append_images=rest,
                   duration=durs_ms, loop=0)
        return buf.getvalue()
    data = enc(128 if shared_palette else 256, shared_palette)
    if len(data) <= max_bytes:
        return data
    for colors in (96, 64, 32):
        data = enc(colors, shared_palette)
        if len(data) <= max_bytes:
            break
    return data


def _gif_preview_scale(frames, preview_w):
    """预览缩放到宽 preview_w（导出传 None 保持原尺寸）。"""
    if not preview_w or not frames:
        return frames
    fw, fh = frames[0].size
    if fw <= preview_w:
        return frames
    r = preview_w / fw
    nh = max(1, int(round(fh * r)))
    return [f.resize((preview_w, nh), Image.LANCZOS) for f in frames]


def _gif_preview_trim(frames, durs_ms, limit):
    """预览抽帧到 ≤limit 帧（等间隔取帧、时长合并，总时长近似不变）。"""
    if len(frames) <= limit:
        return frames, durs_ms
    step = (len(frames) + limit - 1) // limit
    fs = frames[::step][:limit]
    ds = []
    for j in range(0, len(frames), step):
        ds.append(max(1, int(round(sum(durs_ms[j:j + step])))))
    return fs, ds[:len(fs)]


def compose_home_gif(static, user_dir, preview_w=None):
    """主页皮肤.gif：皮肤封面mp4(等比缩放至同宽1242·底层) + 主页皮肤.png(实时) + 气泡框gif@(12,558) w257h276。

    static: _generate_carousel() 的返回（取 '主页皮肤.png'）。
    总时长/帧率以 mp4 为准；无 mp4 退化为单帧静态。preview_w 给预览宽（导出 None=全尺寸）。
    返回 {文件名: GIF bytes}。
    """
    base = static['主页皮肤.png'].convert('RGBA')
    mp4p = os.path.join(user_dir, '皮肤封面.mp4')
    gifp = os.path.join(user_dir, '气泡框.gif')
    has_gif = os.path.isfile(gifp)
    if has_gif:
        gframes, gdurs = load_gif_abs(gifp)
        gtotal = sum(gdurs) or 1
    else:
        gframes, gdurs = [], []

    def pick_bubble(t_ms):
        acc, k = 0, 0
        for k in range(len(gframes)):
            acc += gdurs[k]
            if t_ms < acc:
                break
        return k

    def bubble_at(k):
        return gframes[k].resize((257, 276), Image.LANCZOS)

    if not os.path.isfile(mp4p):
        c = base.copy()
        if has_gif:
            bf = bubble_at(0)
            c.paste(bf, (12, 558), bf)
        return {'主页皮肤.gif': _save_gif_bytes(_gif_preview_scale([c], preview_w), [300],
                                                shared_palette=preview_w is not None)}

    frames, fps = read_mp4_frames(mp4p)
    dur = max(1, round(1000.0 / fps)) if fps else 100
    W, H = base.size
    # 皮肤封面mp4 等比缩放至与背景同宽 1242
    if frames and frames[0].width != W:
        fh = max(1, int(round(frames[0].height * W / frames[0].width)))
        frames = [f.resize((W, fh), Image.LANCZOS) for f in frames]
    out = []
    for i, fr in enumerate(frames):
        c = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        c.paste(fr, (0, 0), fr)
        c = Image.alpha_composite(c, base)          # 主页皮肤.png 压视频上
        if has_gif:
            t = (i * dur) % gtotal
            bf = bubble_at(pick_bubble(t))
            c.paste(bf, (12, 558), bf)
        out.append(c)
    durs = [dur] * len(out)
    if preview_w is not None:
        out, durs = _gif_preview_trim(out, durs, 12)
    out = _gif_preview_scale(out, preview_w)
    return {'主页皮肤.gif': _save_gif_bytes(out, durs,
                                            shared_palette=preview_w is not None)}


def compose_like_gif(static, like_left, like_right, like_text, src_dir, user_dir, preview_w=None):
    """被赞动效.gif：被赞动效.jpg(实时) + 点赞gif@(319,1027) + 胶囊渐变(拉伸到胶囊.png同宽高,蒙版)@(383,1512) + 点赞文字@(383,1511)。

    胶囊+文字透明度按 _like_alpha 随点赞gif帧走。preview_w 给预览宽（导出 None=全尺寸）。
    返回 {被赞动效.gif: bytes, db#hex.png: Image}（db 文件仍为 206×84 源图）。
    """
    base = static['被赞动效.jpg'].convert('RGBA')
    like = os.path.join(user_dir, '点赞.gif')
    db_img = _gradient_rect(like_left, like_right)                            # 206×84 长方形渐变（导出 db）
    mask_path = os.path.join(src_dir, '胶囊.png')
    cap_native = Image.open(mask_path).convert('RGBA').size if os.path.isfile(mask_path) else (479, 84)
    cap_page = _capsule_img(src_dir, like_left, like_right, cap_native[0], cap_native[1])  # 页上胶囊=拉伸到胶囊.png同尺寸
    txt = _load_like_text(src_dir, like_text)
    dbname = 'db#' + ''.join('%02x' % c for c in like_text) + '.png'   # 小写、无加号

    if not os.path.isfile(like):
        c = base.copy()
        return {'被赞动效.gif': _save_gif_bytes(_gif_preview_scale([c], preview_w), [300],
                                                shared_palette=preview_w is not None), dbname: db_img}

    frames, durs = load_gif_abs(like)
    n = len(frames)

    def with_alpha(im, a):
        im = im.copy()
        im.putalpha(Image.eval(im.getchannel('A'), lambda v: int(v * a)))
        return im

    out = []
    for i, f in enumerate(frames):
        c = base.copy()
        c.paste(f, (319, 1027), f)
        a = _like_alpha(i, n)
        if a > 0.01:
            ca = with_alpha(cap_page, a)
            c.paste(ca, (383, 1512), ca)
            if txt is not None:
                t2 = with_alpha(txt, a)
                c.paste(t2, (383, 1511), t2)
        out.append(c)
    if preview_w is not None:
        out, durs = _gif_preview_trim(out, durs, 16)
    out = _gif_preview_scale(out, preview_w)
    return {'被赞动效.gif': _save_gif_bytes(out, durs, shared_palette=preview_w is not None), dbname: db_img}
