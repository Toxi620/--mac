# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

微博预览图配色工具 — 图像处理管线 + Flask Web GUI。三大功能模块：

- **气泡预览图**: 聊天气泡颜色替换、点九拉伸、合成亮/暗双模式、商城展示图、引流位横幅
- **商城轮播图**: 从 `原素材/` 的 5 张底图出发，叠加可调色素材 + 用户上传素材 + 编辑文字，生成 5 张商城预览物料（导出只含其中 4 张，被赞相关拆到「被赞预览」）
- **被赞预览**（独立标签页）: 展示 `被赞动效.jpg` + 预览画板 `chang.png`(510×264) / `fang.png`(228×228)（上下渐变底 + 用户上传 `预览页gif.png`；底色与各自的偏移/缩放网页上可调）。轮播色/点赞三色/编辑文字输入框与商城轮播**共用同一套值**（克隆控件写回主控件）；导出 `11被赞动效.zip` = 被赞动效.jpg + chang.png + fang.png + `db#<点赞文字色hex小写>.png`
- **商城动效 gif**: 在 5 张静态下新增「点赞动效」区 → 实时合成两张动效 `主页皮肤.gif` / `被赞动效.gif`（预览宽 360、导出全尺寸 1242），可调 点赞底部左/右、点赞文字色，上传 气泡框.gif / 皮肤封面.mp4 / 点赞.gif，导出 zip（两 gif + `db#<点赞文字色hex小写>.png`）。**mp4 解码与 gif 编码都依赖 ffmpeg/ffprobe**（打包时必须塞进 bundle）
- **气泡预览图**: 470×470 画板，背景可上传；左右气泡沿用宣传素材（缩到 168 起），左气泡左上角 (72,90) 向右延长、右气泡右上角 (392,230) 向左延长；走 **iOS 点九逻辑**，文字竖直居中、苹方默认 38，可导出 PNG
- **气泡宣传**（原「点九验证」改名）: 分 **安卓 / IOS 两套**预览（同一页上下两组，素材共用、点九逻辑独立）。安卓读 `left_.9.png`/`right_.9.png`（176×176 带黑边，**已冻结**），IOS 读同一份并自动去 1px 边框。**左右文案各自输入互不影响**，手动回车换行、超长自动折行（`#1234567`/纯数字整串不拆、英文按空格、中文逐字、带标点禁则）。安卓留白从**点九黑线框**往里量（右 左45\|30 / 右45\|25 / 上22 下28\|32；左 左63\|43 / 右35\|25），最宽 776；IOS 用**绝对坐标**（拉伸区第82格/第106格、文字区 左75右45 上63下68、最宽 905），并按**字形**对齐、不拉伸时文字居中。有独立取色器（不再跟随气泡预览）。可导出 zip（全尺寸 `左气泡.png` / `右气泡.png`）

支持 macOS (GitHub Actions) 和 Windows (本地 PyInstaller) 单文件打包分发。

## Core Files

| File | Purpose |
|------|---------|
| `pipeline.py` | 核心管线：气泡 + 轮播两张图的合成逻辑 |
| `server.py` | Flask Web 服务：11+ 个 API 路由，端口自动检测 |
| `templates/index.html` | 前端：导航栏、16+ 颜色选择器、字号输入 |
| `build.command` | macOS 打包脚本（含字体复制） |
| `build.bat` | Windows 打包脚本 |
| `fonts/NotoSansSC-Light.ttf` | **气泡宣传中文**用的开源字体（10.1MB，SIL OFL，从 Google Fonts 可变字体抽 wght=300） |
| `fonts/NotoSans-Light.ttf` | **气泡宣传英文/数字**用的开源字体（632KB，SIL OFL，同上一族） |
| `fonts/Roboto-Regular.ttf` | 西文兜底（Apache 2.0） |
| `fonts/PingFang.ttf` | 苹方（10.5MB，iOS 那套 + 气泡预览图用） |
| `原素材/` | 商城轮播图素材（改颜色的/、塞进去替换的/） |

## 仓库与发布

- **git 仓库即本目录**（remote: `https://github.com/Toxi620/--mac.git`）；父目录 `d:\微博预览图\CLAUDE.md` 是内容相同的副本（不入版本库）
- push 到 `main` 会**自动触发** GitHub Actions 打 mac 版（`.github/workflows/build.yml`，也支持手动 Run workflow）；改完代码直接推送即可
- Windows 分发物：`配色工具.exe`（本目录）→ `_win_dist/`（发布目录）→ 父目录 `配色工具_Windows.zip`；mac 分发物：GitHub Actions 的 Artifacts 或 `build.command` 本地产出
- **⚠️ Mac 的 `build.command` 打包完会删除源码**（templates/ static/ fonts/ 及所有 png/py/docx，只留产物）——在 Mac 跑过它之后改代码前先 `git status` 确认源码还在，丢失可从 git 恢复

## Key Architecture

### pipeline.py 结构

**气泡管线 `_generate_core()`** — 6 个 Phase:
1. Phase A: 加载 8 张素材图（优先 `~/Documents/配色工具素材/`）
2. Phase B: `color_replace()` 替换 wz/lj/sk 叠加层
3. Phase C: 点九拉伸 4 个气泡 → 合成亮色模式
4. Phase D: 暗黑模式（独立暗色值 or 回退 ×0.9）
5. Phase E: 商城展示图 420×174（气泡 + 文字叠加预览版）
6. Phase F: 引流位横幅 366×204（渐变背景 + 气泡 + wz_3 文字）

**轮播管线 `_generate_carousel()`** — 5 张图 + 2 张预览画板：
签名含 `edit_size`（可调字号），文字加载优先 `fonts/PingFang.ttf`，回退系统字体
`img5()`（被赞动效.jpg 画板）**不叠** 头像+挂件、顶部装饰（其余图层与卡片背景页一致）

新增参数（服务端统一由 `_carousel_and_like_params()` 解析，4 个调用点共用）：
`like_left/like_right/like_text`（点赞三色）、`prev_top/prev_bottom`（chang/fang 上下渐变底色）、
`prev_chang=(dx,dy,scale)` / `prev_fang=(dx,dy,scale)`（两块画板各自的 1px 微调）
- 返回字典里**键以 `_` 开头的是内部键**（如 `_被赞动效底图`），仅供 `compose_like_gif` 用；`/generate_carousel` 与 `/export_carousel` 都要 `if name.startswith('_'): continue` 跳过
- `_被赞动效底图` = **没叠点赞图层**的干净 bg5。`compose_like_gif` 必须用它当底：`被赞动效.jpg` 里已经烧进了点赞首帧，再叠一遍会出残影
- 末尾追加 `chang.png` / `fang.png`：`_vertical_gradient(上,下,w,h)` 铺底 → `_preview_place()` 算位置 → `_paste_over()` 盖章。素材是用户上传的 `预览页gif.png`（`load_user`），没有就只出渐变底

**`_preview_place(pv, board_w, board_h, target_w, dx=0, dy=0, scale=0)`** — 按 PS 那套流程还原：
1. 600×600 裁掉底部 108 → 600×492
2. 按宽 600→`target_w` 等比缩放整张（`scale` 是网页上按出来的 ±1px，直接加在目标宽上）
3. 「红框」（原 600×600 的正中 360×360）缩放后的中心对齐画板正中心
`dx/dy` 再叠位移；返回 `((x, y), 缩放后的图)`，负坐标由 `_paste_over` 自动裁

**`_paste_over(bg, overlay, pos)`** — 带透明地「盖」到 bg 上（支持负坐标）。
**不要用 `bg.paste(im, pos, im)`**：PIL 带 mask 的 paste 是**逐通道插值**，会把 bg 的 alpha 也插成
`255*(1-m)+a*m` < 255 —— 导出的画板在深色底上看，半透明阴影会显得被加重。改成垫透明图层再
`Image.alpha_composite`，语义等同 PS「正常」叠加，alpha 恒 255。
⚠️ 只给 chang/fang 用；`paste_at()` 保持原样，因为 `卡片背景.png`/`评论气泡.png`/`聊天气泡.png` 依赖原来的透明语义

**动效 gif（阶段二，pipeline.py 尾部）**：
- `compose_home_gif(static, user_dir, preview_w=None)` — 主页皮肤.gif：皮肤封面mp4 等比缩放到同宽1242 铺底 → 主页皮肤.png(实时) → 气泡框.gif 定尺寸 257×276 @(12,558)；总长/帧率以 mp4 为准（fps 来自 ffprobe）
- `compose_like_gif(static, like_left, like_right, like_text, src_dir, user_dir, preview_w=None)` — 被赞动效.gif：被赞动效.jpg(实时) → 点赞.gif @(319,1027) → 胶囊渐变(拉伸到胶囊.png同宽高479×84、蒙版)@(383,1512) → 点赞文字(染点赞文字色)@(383,1511)；胶囊/文字显隐 `_like_alpha()`：第1帧0% → 第4帧100% → 保持满到最后一帧（参考19帧等比换算实际帧数）
- `_capsule_img/_gradient_rect` — 渐变胶囊；导出 `db#<点赞文字色hex小写>.png` = 纯 206×84 长方形渐变（无胶囊镂空）
- `_ffmpeg_bin()` — 定位 ffmpeg/ffprobe：bundle(s._MEIPASS/exe同目录) → 脚本同目录 → PATH；`read_mp4_frames()` 用 ffmpeg 解 mp4（**不用 cv2**）；`_save_gif_bytes()` 用 ffmpeg palettegen/paletteuse 编码（预览 bayer、导出 sierra2_4a），>8MB 自动“降色+抽帧减半”压缩，无 ffmpeg 回退 PIL

### server.py 特性

- 端口自动检测：5001 被占用时尝试 5002、5003...；**debug 重载用 `WALLPAPER_PORT` 环境变量记住端口，避免每次改代码重启后端口漂移**（reloader 子进程复用同一端口）
- 打包版 `debug=False`，本地开发 `debug=True`
- **UI 状态持久化**：存档在 `~/Documents/配色工具素材/state.json`（`STATE_FILE`）。`GET /` 把存档 + 已上传素材清单塞进模板（`state=` / `user_files=`）；前端每次改色/改字/切面板去抖 500ms `POST /state` 一份，重开网页颜色、编辑文字、气泡宣传文案、字号、「暗色是否跟随浅色」、上次停留的面板全部恢复；用户传过的素材按钮显示绿框「已上传」（素材本身一直存在 `USER_DATA_DIR`，本来就不会丢）
- API 路由：
  - `GET /` 首页（渲染 index.html）
  - `GET /state` 读存档 + 已上传素材清单；`POST /state` 保存存档（临时文件 + `os.replace` 原子写）
  - `POST /generate` 气泡预览缩略图；`POST /export` 导出气泡高清 ZIP
  - `POST /generate_carousel` 轮播预览（跳过 `_` 内部键，宽 >600 的等比缩到 600）；`POST /export_carousel` 导出商城物料 ZIP
    - ZIP 结构：**根** = 4 张静态画板（`主页皮肤.png`/`卡片背景.png`/`聊天气泡.png`/`评论气泡.png`）；被赞相关（被赞动效.jpg/chang/fang/db#）已拆到 `/export_like`
    - 导出前清残留：删 out_dir 里的 `被赞动效.jpg`/`chang.png`/`fang.png` 和 `11被赞动效/` 整个文件夹（旧版导出产物不删会混进 zip）
  - `POST /export_like` 被赞预览导出：`11被赞动效.zip` = 根下 4 个文件（`被赞动效.jpg` + `chang.png` + `fang.png` + `db#<点赞文字色hex小写>.png` 206×84 左右渐变），纯内存打包（参考 export_promo）不落盘
  - 两个轮播接口的入参都由 **`_carousel_and_like_params(data)`** 统一解析（颜色 + 编辑文字/字号 + 点赞三色 + `预览底色上/下` + `chang偏移X/Y/缩放` + `fang偏移X/Y/缩放` → 打包成 `pvc`/`pvf` 两个三元组），加参数只改这一处
  - `POST /generate_gif` 动效预览（全宽360 两 gif 一并返回）；`POST /export_gif` 导出 动效物料.zip（两 gif 全尺寸 + db#.png）
  - `POST /generate_promo` 气泡宣传预览（参数：左文字/右文字/字号/文字色/**ios**；`ios=true` 走 IOS 那套逻辑）；`POST /export_promo` 导出 zip（`气泡宣传.zip` / `气泡宣传IOS.zip`，IOS 的图名带 `_IOS`）
  - `POST /upload_carousel` 轮播素材上传（name 白名单，含 头像挂件/方图/star/gua/主页皮肤/聊天头像 + 动效三样 气泡框.gif/皮肤封面.mp4/点赞.gif）；`POST /upload_bubble` 气泡素材上传（left/right/bg_0/bg_1）
  - `POST /upload_promo_bubble` **气泡宣传专用**素材上传（side=left/right）：传 176×176 带黑边的图 → 写 3 份：`<side>_.9.png`（安卓+iOS+气泡预览图 共用）、`<side>_ios.png`（兼容旧路径）、`<side>_promo_src.png`（原图备份）；非 176 的按无边框处理，安卓那份自动补 1px 透明边框。返回 `thumb`(base64) 供前端回显
  - `POST /generate_bubble_preview` 气泡预览图预览（参数：左文字/右文字/字号/文字色）→ 返回 `preview`(base64)
  - `POST /export_bubble_preview` 导出 470×470 全尺寸 PNG（`气泡预览图.png`）
  - `POST /upload_preview_bg` 气泡预览图背景上传（PNG/JPG 都行，合成时缩放到 470×470）
  - `POST /shutdown` 关闭服务
- **本地开发禁缓存**：`after_request` 钩子在非 frozen 时给所有响应加 `Cache-Control: no-store` 等头，避免改了模板刷新看不到变化（打包版不加）

### 气泡宣传模块（原「点九验证」）

`_generate_promo(left_text, right_text, font_size, text_color, ios=False)`，两套预览素材与点九逻辑各自独立：

- **安卓**（`ios=False`）：`left_.9.png` / `right_.9.png`（176×176 带 1px 黑边）。**已冻结，不再修改**。
- **IOS**（`ios=True`）：读**同一份** `left_.9.png` / `right_.9.png`，`load_9()` 里自动 `crop(1,1,175,175)` 去掉那 1px 黑边 → 内部 174×174。

公共部分（两套共用）：

- **换行**：手动回车（`\n`）优先；超长再自动折行。折行规则（`wrap_to_width` + `_tokens`）：
  - **原子串整体不拆**：`#1234567`（`#`/`@`/`$` + 字母数字）和纯数字串整体移到下一行；自身超宽才退化成逐字拆
  - 英文单词优先在空格处断（带回退，不劈单词），中文逐字断
  - **标点禁则**：`，。！？` 等不置行首（跟前一字一起带到下行）、`（「` 等不置行末（推到下行）——`PROMO_NO_LINE_START` / `PROMO_NO_LINE_END`
- **字体**：安卓 = 中文 **Noto Sans SC Light** + 英文数字 **Noto Sans Light**（都是开源，见「字体体系」节）；**iOS = 中英文都用苹方**(`PingFang.ttf`)。逐字符按所属字体渲染，两端一致
- **字号**：安卓默认 `PROMO_FONT_SIZE`=50，iOS 默认 `PROMO_IOS_FONT_SIZE`=50（各自独立）
- **字间距**：安卓 `PROMO_LETTER_SPACING`=1，iOS `PROMO_IOS_LETTER_SPACING`=0
- **行高**：`PROMO_LINE_H_RATIO`=0.9014（行高 = 字体自然行高 × 系数）
- 文字色 = 气泡宣传自己的取色器（`colorNpText`，**不再跟随气泡预览**），安卓/iOS 共用
- 导出 → zip（`气泡宣传.zip` / `气泡宣传IOS.zip`，图名带 `_IOS` 后缀）

**安卓留白（已冻结）**——基准 = 点九**黑线框**，往里缩固定 px：

| | 左留白（不拉伸 \| 拉伸） | 右留白（不换行 \| 换行） | 上 | 下（不换行 \| 换行） |
|---|---|---|---|---|
| 右气泡 | `PROMO_INSET_L`=45 \| `_STRETCH`=30 | `PROMO_INSET_R`=45 \| `_WRAP`=25 | `PROMO_INSET_T`=22 | `PROMO_INSET_B`=28 \| `_WRAP`=32 |
| 左气泡 | `PROMO_L_INSET_L`=63 \| `_STRETCH`=43 | `PROMO_L_INSET_R`=35 \| `_WRAP`=25 | `PROMO_L_INSET_T`=22 | `PROMO_L_INSET_B`=28 \| `_WRAP`=32 |

- `edge_l = bb_l + 左留白`、`edge_r = 内部宽−bb_r + 右留白`
- 「拉伸/不拉伸」判据：文字宽 > `PROMO_STRETCH_TEXT_W`=65px
- **折行上限 = 整个气泡总宽** `PROMO_MAX_BUBBLE_W`=776（含 1px 黑边）：可用文字宽 = `776 − edge_l − edge_r`；折行时气泡直接拉到 776
- **右侧退让**：先用「不换行档」，放不下退让到「换行档」，仍放不下才真折行
- 下限 = 素材本身 176×176（单字不压缩）
- 文字**一律左对齐**到内容框左缘

**IOS 规格**（绝对坐标写死，不分档、不退让）：

| 项 | 值 | 常量 |
|---|---|---|
| 纵向拉伸区 | 上往下第 **82** 格（1px） | `PROMO_IOS_STRETCH_Y` |
| 横向拉伸区 | 右气泡 左往右第 **106** 格；左气泡镜像 右往左第 **106** 格 | `PROMO_IOS_STRETCH_X` / `PROMO_IOS_L_STRETCH_X`=71 |
| 文字区 | 右气泡 左 **75** / 右 **45**；左气泡镜像 左 **45** / 右 **75** | `PROMO_IOS_TEXT_L` / `_R` |
| 上下留白 | 上 **63** / 下 **68** | `PROMO_IOS_TEXT_T` / `_B` |
| 最宽（含黑边） | **905** | `PROMO_IOS_MAX_W` |

- 拉伸区格号是**带 1px 黑边的文件**上的 1-based 值，转内部 0-based 要 **−2**（−1 转 0-based、−1 去边框）；`load_9` 已去过边框，所以 `iw = img.width` **不能再减 2**（减两次会切块错位、画面变形）
- **按字形对齐**（不是行盒）：`ink_top` 抬掉字形距行盒顶的空隙 → 看得见的第一笔正好落在 `edge_t`；高度锚定「**末行字形底** + `edge_b`」，所以换行后「最后一笔到气泡底」恒为 68px
- **不拉伸时文字居中**：气泡宽度还停在素材原宽（`target_w <= min_w`）且没折行时，**每行各自水平居中**于内容区；一旦被撑开或折行，回到左对齐

### 气泡预览图模块（470×470 画板）

`_generate_bubble_preview(left_text, right_text, font_size, text_color)` + `/generate_bubble_preview` / `/export_bubble_preview` / `/upload_preview_bg`：

- 画板 **470×470**，背景优先读用户上传的 `气泡预览图背景.png`（`BUBBLE_PREVIEW_BG_NAME`），没有就纯白；上传的图会自动缩放到 470×470
- **气泡素材沿用气泡宣传那套** `left_.9.png` / `right_.9.png`
- **尺寸做法**：素材去 1px 黑边得 174×174 → **整体等比缩到 168×168**（`k = 168/174 = 0.9655`），点九拉伸区与文字留白**全部 × k**
- **点九逻辑用 iOS 那套**（不是安卓）：拉伸区 纵向第82格 / 横向右第106格·左第71格，再 ×k；文字留白用 `PROMO_IOS_TEXT_*`（左75/右45/上63/下68，左气泡左右镜像）再 ×k
- **摆位**：左气泡**左上角 (72,90)、向右延长**；右气泡**右上角 (392,230)、向左延长**（`BUBBLE_PREVIEW_LEFT_XY` / `_RIGHT_XY`）
- 文字**左右分开输入**、**苹方/Noto、默认字号 38**、画板内自动折行（可用宽 = 画板余量 − 左右留白）
- **文字竖直居中**：算文字块**字形**实占高度，在气泡里上下均分（水平仍左对齐到 `edge_l`）
- **168 只是起点**：留白合计 115.9px，所以 168 的气泡只装得下 1 个中文字；2 字起气泡九宫格拉伸变大（留白保持固定，因为固定区不随拉伸移动）
- 可用宽上限：左气泡 `470−72=398`、右气泡 `392`，超了折行（不折会跑出画板）

### 前端 (templates/index.html)

- **自定义取色面板**：点色块弹出面板，hex 输入为主（顶部大输入框 + 色相条 + 饱和度方块 + R/G/B 次级 + 底部「💧 吸管 | 完成」）；原生 `<input type="color">` 已隐藏——浏览器原生取色器默认显示 RGB，且无法用网页代码修改其显示格式
- **吸管取色**：优先 `window.EyeDropper`（Chrome/Edge，可吸整个屏幕）；不可用时回退 `getDisplayMedia` 截当前标签页 → 全屏 `<img id="cpEyeLayer">` 覆盖层点哪取哪（Firefox/Safari）。吸管激活时 `cpEyeOn` 会挡掉「点面板外关闭」、`body.cp-eyedrop` 全局十字光标；Esc 或再点按钮取消
- 13 个颜色共用同一个取色面板，JS 自动为每个 `input[type=color]` 生成色块按钮（`.cp-swatch`）并同步颜色；改色通过给隐藏 input 派发 `input` 事件驱动原有监听（暗色自动跟随、实时预览）
- **商城轮播页自上而下**：轮播色 grid（多 点赞底部颜色左/右/点赞文字色 3 项，色板自动生成）→ 编辑行 → 上传行（预览页gif 上传已移到被赞预览页）→ `#carouselPreviews`（4 张静态）→ `#carouselGifPreviews`（2 列动效，inline `max-width:760px` 可调宽）；动效/上传/改色走 `doCarouselPreview()` → `scheduleCarouselGif()` 去抖调 `/generate_gif`（busy 锁防并发，预览全宽 360）。**gif 只在商城轮播页刷**：`doCarouselPreview` 里 `currentTab==='carousel'` 才 `scheduleCarouselGif()`，在被赞页调色不烧 ffmpeg，切回来时 `switchTab` 自动补刷
- **被赞预览页自上而下**：轮播色 grid 副本 → 点赞动效三色副本 → 编辑行（含「📥 导出」= `/export_like`）→ 上传行（方图/预览页gif）→ `#likeBoardsWrap` grid：`'like chang panel' / 'like fang panel'`（左 `#likePreviews` 被赞动效.jpg 跨两行；中 chang 上、fang 下同宽，各带微调行；右「🖼 预览底色」面板）。微调按钮事件委托挂 `#likeBoardsWrap` 上
- **被赞预览的克隆控件**：轮播色/点赞三色/编辑文字是商城轮播控件的**副本**（`lkBg`/`lkText`/…，映射表 `LK_CLONES`），值共用同一套存档键。克隆 `input` → 写回主控件（`carBg` 等）→ `dispatchEvent('input')` 走主控件原有链路 → `syncLikeClones()` 把所有克隆刷齐；进被赞页时 `switchTab` 也调一次 `syncLikeClones()`。⚠️ 初始化时先 `syncLikeClones()` 再 `buildSwatches()`，色块首帧颜色才对
- **chang/fang 各自的微调行**：`pvBoardBlock(name, url)` 渲染成 `.pv-block` = 画板卡片 + 一行 `.pv-ctrl`（↑↓←→ 各 1px、`−/＋` 缩放 1px、重置）。状态在 `carPv = {chang:{dx,dy,s}, fang:{...}}`
  - ⚠️ 画板卡片每次刷新都整个重建，所以监听**必须用事件委托**挂在 `#carPreviewBoards` 上（`e.target.closest('[data-act]')`），不能挨个绑按钮
  - 状态键：`chang偏移X/Y/缩放`、`fang偏移X/Y/缩放`（存 `state.json`，`INITIAL_STATE` 里回读）
  - 点微调按钮 → 改 `carPv` → `updateCarouselHex()` 刷数字 → `doCarouselStaticPreview()`（**只重画静态，不重算 gif**）→ `saveState()`
  - `.pv-block` 统一给画板图 `height:220px`（`object-fit:contain` 不拉伸）→ 两块画板高对齐，下面两行按钮才齐；`.pv-block` 底部留 `margin-bottom:20px`
- **气泡宣传页自上而下**：独立取色器 `colorNpText` → 素材上传行（`.promo-upload`，安卓/iOS 共用）→ 安卓那组（左/右 textarea + 字号 + 导出 + `#ninepatchPreviews`）→ 虚线分隔 → **IOS 那组**（`npTextLIos` / `npTextRIos` / `npFontSizeIos` / `#ninepatchPreviewsIos`）。两组各自去抖 300ms 调 `/generate_promo`（IOS 带 `ios:true`），改共享的文字色会**两套一起刷**
- **⚠️ 两个易踩的坑**（都修过）：
  1. **去抖计时器必须先声明**：`switchTab()` 里 `clearTimeout(npDebounce)`，若 `let npDebounce` 写在 `switchTab` **后面**，进页面时切到气泡宣传页会撞 TDZ 抛 `ReferenceError` → **整个初始化中断、预览不渲染**（要动一下输入框才出来）。计时器声明统一提到 `switchTab` 之前
  2. **`switchTab` 三个页都要有分支**：漏掉 `bubble` 的话，从气泡宣传切回气泡概览不会刷新预览
  3. **`collectState()` 别整个 merge `getNinepatchParams()`**：它里面的「文字色」是**气泡宣传**自己的取色器，会把 `getColors()` 的同名键（**气泡预览**的文字色）覆盖掉 → 存档里存错值、重开网页气泡预览被灌成宣传的色。要**逐项写**，宣传的文字色用独立键 **`宣传文字色`**（模板读的也是这个键）
  4. **上传素材后要刷新所有用到它的预览**：`uploadPromoBubble` 一开始只刷了安卓 + IOS，漏了**气泡预览图**（也用同一份素材）→ 传了新图预览图不变

### 字体体系

编辑文字加载顺序：
1. `WORK_DIR/fonts/PingFang.ttf`（打包带入的苹方）
2. `C:/Windows/Fonts/msyh.ttc`（Windows 降级）
3. `ImageFont.load_default()`（8px 降级）

**气泡宣传 / 气泡预览图**另有专属字体链（逐字符按所属字体渲染）：

| 用途 | 常量 | 加载顺序 |
|---|---|---|
| 气泡宣传·安卓中文 | `PROMO_FONT_CN` | **`fonts/NotoSansSC-Light.ttf`**（开源 OFL）→ `msyhl.ttc` → 苹方 |
| 气泡宣传·安卓英文 | `PROMO_FONT_EN` | **`fonts/NotoSans-Light.ttf`**（开源 OFL）→ `Roboto-Regular.ttf` → `segoeui.ttf` → 苹方 |
| 气泡宣传·iOS | `PROMO_IOS_FONT` | 苹方 → 微软雅黑 |
| 气泡预览图 | 代码内 `load_font()` | 苹方 → 微软雅黑 |

**为什么优先开源字体**：微软雅黑 / Segoe UI / 苹方都是**专有字体**，不能合法分发到对方平台（Windows 用微软的、Mac 用苹果的，两端永远不一致）。改用 **Noto Sans**（SIL OFL）+ **Roboto**（Apache 2.0）后 **Windows 与 Mac 完全一致**、也没有授权问题。

- `fonts/NotoSansSC-Light.ttf`（10.1MB）与 `fonts/NotoSans-Light.ttf`（632KB）都是从 Google Fonts 的可变字体 `NotoSansSC[wght].ttf` / `NotoSans[wdth,wght].ttf` 用 `fontTools.varLib.instancer` 抽出 **wght=300** 的静态字重（源在 `github.com/google/fonts`，raw 可直接下）
- ⚠️ 抽完记得**改 name 表**（`usWeightClass=300` 但名字还是 Thin，PIL 的 `getname()` 会误导）
- `msyhl.ttc` / `segoeui.ttf` 仅作回退保留（Windows 上万一 Noto 缺失时才用）
- 中文字宽一致（50号 = 50px/字），但**数字宽度不同**（雅黑 19 / 苹方 30 / Noto 27），换字体后带数字的文案宽度会变

字号可在网页上实时调整（商城轮播编辑文字默认 36；气泡宣传安卓/iOS 各默认 50；范围 12-120）。

## Common Workflows

### 启动 Web 服务
```bash
python server.py
# 访问 http://localhost:5001
```

### macOS 打包（GitHub Actions）
```bash
git push
# 打开 https://github.com/Toxi620/--mac/actions
# 点 Run workflow → 下载 Artifacts
```

### Windows 打包（本地）
```bash
# 推荐：直接运行打包脚本（不会删除源码，可重复运行）
build.bat
# ⚠️ build.bat 需要本机有 ffmpeg/ffprobe（winget install Gyan.FFmpeg），并已用
#    --add-binary 把它们打进 exe —— 动效 gif 依赖它们（运行时经 _ffmpeg_bin() 在 _MEIPASS 找）
# 手动命令（等效，产物 配色工具.exe 在仓库根目录）：
python -m PyInstaller --onefile -w --distpath . --add-data "templates;templates" --add-data "static;static" --add-data "原素材;原素材" --add-data "fonts;fonts" --add-data "bg_0.png;." --add-data "bg_1.png;." --add-data "wz_0.png;." --add-data "lj_0.png;." --add-data "sk_0.png;." --add-data "left_.9.png;." --add-data "right_.9.png;." --add-data "wz_3.png;." --add-data "商城6字展示420X174.png;." --add-data "代码文档.docx;." --add-data "pipeline.py;." --add-data "version.txt;." --add-binary "<ffmpeg.exe路径>;." --add-binary "<ffprobe.exe路径>;." --hidden-import numpy --name "配色工具" server.py
```

### macOS 打包要点（GitHub Actions）
- `build.command` 会先下载 mac 静态 ffmpeg/ffprobe（evermeet 7.1 到 `/tmp/ffmpeg-bundle`），再用 `--add-binary` 打进 bundle；构建机需联网
- ⚠️ build.command 打包完会删除源码（templates/ static/ fonts/ 及 png/py/docx），Mac 本地跑过改代码前先 `git status`

## 注意事项
- **docx 色值替换**: 模板含 6 个色值（亮 `#6985c5`/`#97979e`/`#d1e2fe` + 暗 `#7ea6d2`/`#afb0bf`/`#546c94`），`main()` 全部替换；用占位符两段替换，防止新色值恰好等于另一待替换旧色值时被二次替换
- **轮播「聊天气泡.png」**: 背景复用气泡管线「页面1普通模式」（缩放到 1242×2688 裁剪），文字色/tag色/tag底板色均取气泡面板当前值——前端 `getCarouselColors()` 会随请求带上 `文字色` 字段；上层 759×207 气泡点九图优先读用户上传的 `left_.9.png`（`user_dir`），与气泡预览一致
- **轮播「主页皮肤.png」背景可上传**: `img1()` 用 `load_override()` 加载背景——优先 `user_dir` 用户上传的 `主页皮肤.png`，没有则回退 `原素材/主页皮肤.png`；上传走 `/upload_carousel`（name 白名单已含 `主页皮肤.png`），前端工具栏有「⬆ 主页皮肤背景」按钮。同样的 `load_override` 机制可扩展给 `卡片背景.png` / `评论气泡.png`
- **气泡底框五选一**: `气泡底框颜色`（`CAROUSEL_BUBBLE_PRESETS`）改为预置 5 色 `#FF8F56/#FEAD3A/#DEC84C/#A55DAB/#D04666`，前端渲染为圆点选择器（`.preset-swatch`），默认 `#FF8F56`；该颜色同时作用于 pic1.png 与评论气泡底色1/2
- **苹方字体必须打包**: GitHub Actions macOS 无 PingFang，需下载/预置 `fonts/PingFang.ttf`，用 `--add-data "fonts;fonts"` 打进包
- **Windows 打包素材路径**: 轮播素材必须用 `--add-data "原素材;原素材"`（打进 `_MEIPASS/原素材`），不要用 `../02/原素材;02/原素材`——frozen 后 `_get_carousel_dir()` 只找 `_MEIPASS/原素材`；字体也不能漏（`fonts;fonts`）
- **PIL paste 不带 mask**: `result.paste(p, (x, y))` 保持 alpha。`result.paste(img, pos, img)` 会**稀释底图 alpha**（`255*(1-m)+a*m`），导出的图在深色底上会显出「阴影被加重」——要盖图上透明就用 **`_paste_over()`**
- **composite_scene**: 末尾强制 `arr[:,:,3]=255`
- **darken_overlay**: 阈值 alpha>200，半透明边缘不动
- **首次打开 Mac 包**: 右键 → 打开 → 仍要打开
- **ffmpeg/ffprobe 是硬依赖**: mp4 解码（`read_mp4_frames`）与 gif 编码（`_save_gif_bytes`→ffmpeg palettegen/paletteuse）都要它；Windows/mac 打包都必须用 `--add-binary` 塞进 bundle，运行时 `_ffmpeg_bin()` 依次找 `_MEIPASS`/exe同目录/脚本同目录/PATH。无 ffmpeg 时 gif 会退回 PIL 编码（有色差）或无法解码 mp4
- **db# 命名**: 导出的胶囊渐变图固定 `db#` + 点赞文字色 hex **全小写、无 # 无 +**（如 `db#ff5582.png`），内容是**纯 206×84 长方形渐变**（胶囊镂空只在 gif 内合成）
- **动效 gif 尺寸**: 预览宽 360 + 抽帧（主页≤12、点赞≤16）；导出全尺寸 1242，单文件超 8MB 自动“降色+抽帧减半”压缩
- **阶段二新素材（从 `d:\微博预览图\03\` 拷入 原素材）**: `图层 1086.png`/`评论放大.png`/`图层 1088.png`/`1.png`(42×42)→原素材根目录；`胶囊.png`→原素材根目录；`点赞文字.png`→原素材/改颜色的/（合成时染点赞文字色）；头像上传=用户 `聊天头像.png` 存 USER_DATA_DIR，合成时裁透明边→圆形内切 wh 贴（坐标锚点=外接正方形左上角）
- **评论页叠层**（img3）：旧组件保留，然后严格按需求文本顺序自下而上叠（头像→评论放大→头像→图层1088），会有遮挡属预期
- **⚠️ 导出目录名对不上**：需求文本（`03/替换头像.txt`）写的是 **`11被赞动态`**，代码里是 **`11被赞动效`**（`server.py` 的 `sub_dir`）。两边说好统一哪个再改，别单方面重命名（下游可能已经按现有名字接了）
- **chang/fang 的来源**：`chang.png` = 510×264 画板、`fang.png` = 228×228 画板，素材都是**用户上传的 `预览页gif.png`**（USER_DATA_DIR），`原素材/` 里没有；没传就只输出渐变底
- **预览底色上/下**（`DEFAULT_PREVIEW_GRAD_TOP`=`#fefae8` / `_BOTTOM`=`#ecfafe`）只影响 chang/fang 这两张静态画板，改它**不需要重算 gif**（前端走 `doCarouselStaticPreview()`）
