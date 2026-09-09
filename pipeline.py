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
        bg = paste_at(bg, load_color('评论气泡底色2.png', bubble_bg_color), 171, 570)
        bg = paste_at(bg, load_color('评论气泡底色1.png', bubble_bg_color), 413, 1087)
        bg = paste_at(bg, load_color('评论气泡-我也想要！.png', want_color), 446, 1115)
        gua = load_user('gua#ff5582.png')
        bg = paste_at(bg, gua, 505, 616, 139, 54)
        bg = paste_at(bg, gua, 639, 1145)
        # 需求新增，严格照 txt 顺序自下而上贴（会有遮挡属预期）
        bg = paste_avatar(bg, 40, 1074, 116)
        bg = paste_at(bg, load_src('评论放大.png'), 0, 774)
        bg = paste_avatar(bg, 212, 998, 170)
        bg = paste_at(bg, load_src('图层 1088.png'), 319, 1106)
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


def _generate_promo(left_text='', right_text='', font_size=36,
                    text_color=(51, 51, 51)):
    """气泡宣传：左/右气泡按各自文案生成，左气泡左对齐、右气泡右对齐。

    - 源图：left_.9.png / right_.9.png（优先用户上传，回退打包目录），176×176
    - 采用「商城6字展示(预览)」的生成思路：气泡按文案包字（pad+文字宽/高），
      不做严格点九内容区填充；不足时由素材固定区下限兜底。
    - 换行只认输入里的手动换行（\n），不再自动截断。
    - 文字：苹方（商城轮播同款字体），文字块在内容区内垂直居中，
      左气泡靠内容区左缘、右气泡靠内容区右缘，两侧各留 PROMO_TEXT_INSET_X px。
    返回 {"左侧气泡": Image, "右侧气泡": Image}。
    """
    from PIL import ImageDraw, ImageFont

    def load_9(n):
        p = os.path.join(USER_DATA_DIR, n)
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
        return Image.open(os.path.join(WORK_DIR, n)).convert('RGBA')

    def load_font(size):
        for fp in [os.path.join(WORK_DIR, 'fonts', 'PingFang.ttf'),
                   'C:/Windows/Fonts/msyh.ttc']:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def split_lines(text):
        """只在输入框手动换行处断行（不再按字数自动截断）。"""
        return text.split('\n')

    def build(img, text, align):
        np_params = parse_nine_patch(img)
        pl, pr = np_params['pad_left'], np_params['pad_right']
        pt, pb = np_params['pad_top'], np_params['pad_bottom']
        min_w = np_params['fixed_left'] + np_params['fixed_right']
        min_h = np_params['fixed_top'] + np_params['fixed_bottom']

        lines = split_lines(text) if text else []
        font = load_font(font_size)
        if lines:
            ascent, descent = font.getmetrics()
            line_h = ascent + descent
            text_w = max(font.getlength(ln) for ln in lines)
        else:
            line_h = text_w = 0
        text_h = line_h * len(lines)

        # ≥2 行时首行上/末行下各加额外间距；单行仍整体居中不留
        vinset = PROMO_TEXT_INSET_Y if len(lines) > 1 else 0
        target_w = max(min_w, int(text_w) + pl + pr + 2 * PROMO_TEXT_INSET_X)
        target_h = max(min_h, text_h + 2 * vinset + pt + pb)
        bubble = nine_patch_scale(img, target_w, target_h, np_params)
        if lines:
            draw = ImageDraw.Draw(bubble)
            # 文字块在内容区内垂直居中，并保证上/下至少 vinset
            content_h = target_h - pt - pb
            top = pt + vinset + max(0, (content_h - 2 * vinset - text_h) // 2)
            for i, ln in enumerate(lines):
                cy = top + i * line_h + line_h // 2
                if align == 'right':
                    # 右气泡：靠内容区右缘 + 内侧留白，锚点 rm
                    draw.text((target_w - pr - PROMO_TEXT_INSET_X, cy), ln,
                              font=font, fill=text_color + (255,), anchor="rm")
                else:
                    # 左气泡：靠内容区左缘 + 内侧留白，锚点 lm
                    draw.text((pl + PROMO_TEXT_INSET_X, cy), ln, font=font,
                              fill=text_color + (255,), anchor="lm")
        return bubble

    left = build(load_9('left_.9.png'), left_text, 'left')
    right = build(load_9('right_.9.png'), right_text, 'right')
    return {"左侧气泡": left, "右侧气泡": right}


PROMO_TEXT_INSET_X = 14  # 气泡宣传：文字与内容区左右边缘之间的留白（px）
PROMO_TEXT_INSET_Y = 8   # 气泡宣传：≥2 行时，首行上/末行下的额外间距（px）


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
            cw = Image.new('RGBA', (420, 174), (0, 0, 0, 0))
            cw.paste(bub, (0, round((174 - bub_h) / 2.0)), bub)   # 纵向居中
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
