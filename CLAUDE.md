# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

微博预览图配色工具 — 图像处理管线 + Flask Web GUI。三大功能模块：

- **气泡预览图**: 聊天气泡颜色替换、点九拉伸、合成亮/暗双模式、商城展示图、引流位横幅
- **商城轮播图**: 从 `原素材/` 的 5 张底图出发，叠加可调色素材 + 用户上传素材 + 编辑文字，生成 5 张商城预览物料
- **点九验证**: 严格按点九标准把 `left_.9.png` / `right_.9.png`（176×176）拉伸成左右气泡预览，**每行 10 个字、超出自动换行**（宽度固定约 10 字宽，高度随行数增长）；文字**全部左对齐**（靠内容区左边缘），恰好填满右/下边线标记的内容区、无额外留白，气泡 = 内容区 + 点九 padding，且不小于上/左拉伸区固定部分，用苹方字体绘制（文字内容、字号、文字色可调）。**只忠实复现点九结果，不做美化**

支持 macOS (GitHub Actions) 和 Windows (本地 PyInstaller) 单文件打包分发。

## Core Files

| File | Purpose |
|------|---------|
| `pipeline.py` | 核心管线：气泡 + 轮播两张图的合成逻辑 |
| `server.py` | Flask Web 服务：9 个 API 路由，端口自动检测 |
| `templates/index.html` | 前端：导航栏、13+ 颜色选择器、字号输入 |
| `build.command` | macOS 打包脚本（含字体复制） |
| `build.bat` | Windows 打包脚本 |
| `fonts/PingFang.ttf` | 打包进应用的苹方字体（10.5MB，来自 GitHub） |
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

**轮播管线 `_generate_carousel()`** — 5 张图：
签名含 `edit_size`（可调字号），文字加载优先 `fonts/PingFang.ttf`，回退系统字体

### server.py 特性

- 端口自动检测：5001 被占用时尝试 5002、5003...；**debug 重载用 `WALLPAPER_PORT` 环境变量记住端口，避免每次改代码重启后端口漂移**（reloader 子进程复用同一端口）
- 打包版 `debug=False`，本地开发 `debug=True`
- 9 个 API 路由：
  - `GET /` 首页（渲染 index.html）
  - `POST /generate` 气泡预览缩略图；`POST /export` 导出气泡高清 ZIP
  - `POST /generate_carousel` 轮播预览；`POST /export_carousel` 导出商城物料 ZIP
  - `POST /generate_ninepatch` 点九验证预览（参数：文字/字号/文字色）
  - `POST /upload_carousel` 轮播素材上传（name 白名单）；`POST /upload_bubble` 气泡素材上传（left/right/bg_0/bg_1）
  - `POST /shutdown` 关闭服务

### 点九验证模块

`_generate_ninepatch()` + `/generate_ninepatch`：

- 源图 `left_.9.png` / `right_.9.png`（176×176，优先用户上传的 `USER_DATA_DIR`，回退 `WORK_DIR`）
- `parse_nine_patch()` 读上/左拉伸区 + 右/下内容 padding → `nine_patch_scale()` 只拉伸标记区域
- **气泡尺寸自动生成（严格点九，无额外留白）**：每行 `NINEPATCH_LINE_CHARS=10` 字、超出自动换行（按字符数切片）；行高 = `font.getmetrics()` 的 ascent+descent，行宽 = 各 line bbox 最大宽；内容区 = 文字尺寸（恰好填满），气泡 = 内容区 + pad_l/pad_r/pad_t/pad_b，并 `max(固定区最小尺寸)` 兜底（fixed_left+fixed_right / fixed_top+fixed_bottom）。**刻意不做留白美化，忠实复现点九结果，可能显得很挤**
- 文字加载顺序：`WORK_DIR/fonts/PingFang.ttf` → `C:/Windows/Fonts/msyh.ttc` → 默认字体
- 文字**全部左对齐**：每行 `draw.text((pad_left, 行中心y), ..., anchor="lm")`，紧贴内容区左边缘
- 前端参数：文字内容/字号/文字色（左右气泡宽高不手调，随文字实时变化）

### 前端 (templates/index.html)

- **自定义取色面板**：点色块弹出面板，hex 输入为主（顶部大输入框 + 色相条 + 饱和度方块 + R/G/B 次级 + 完成按钮）；原生 `<input type="color">` 已隐藏——浏览器原生取色器默认显示 RGB，且无法用网页代码修改其显示格式
- 13 个颜色共用同一个取色面板，JS 自动为每个 `input[type=color]` 生成色块按钮（`.cp-swatch`）并同步颜色；改色通过给隐藏 input 派发 `input` 事件驱动原有监听（暗色自动跟随、实时预览）

### 字体体系

编辑文字加载顺序：
1. `WORK_DIR/fonts/PingFang.ttf`（打包带入的苹方）
2. `C:/Windows/Fonts/msyh.ttc`（Windows 降级）
3. `ImageFont.load_default()`（8px 降级）

字号可在网页上实时调整（默认 36，范围 12-120）。

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
# 手动命令（等效，产物 配色工具.exe 在仓库根目录）：
python -m PyInstaller --onefile -w --distpath . --add-data "templates;templates" --add-data "static;static" --add-data "原素材;原素材" --add-data "fonts;fonts" --add-data "bg_0.png;." --add-data "bg_1.png;." --add-data "wz_0.png;." --add-data "lj_0.png;." --add-data "sk_0.png;." --add-data "left_.9.png;." --add-data "right_.9.png;." --add-data "wz_3.png;." --add-data "商城6字展示420X174.png;." --add-data "代码文档.docx;." --add-data "pipeline.py;." --hidden-import numpy --name "配色工具" server.py
```

## 注意事项
- **docx 色值替换**: 模板含 6 个色值（亮 `#6985c5`/`#97979e`/`#d1e2fe` + 暗 `#7ea6d2`/`#afb0bf`/`#546c94`），`main()` 全部替换；用占位符两段替换，防止新色值恰好等于另一待替换旧色值时被二次替换
- **轮播「聊天气泡.png」**: 背景复用气泡管线「页面1普通模式」（缩放到 1242×2688 裁剪），文字色/tag色/tag底板色均取气泡面板当前值——前端 `getCarouselColors()` 会随请求带上 `文字色` 字段；上层 759×207 气泡点九图优先读用户上传的 `left_.9.png`（`user_dir`），与气泡预览一致
- **轮播「主页皮肤.png」背景可上传**: `img1()` 用 `load_override()` 加载背景——优先 `user_dir` 用户上传的 `主页皮肤.png`，没有则回退 `原素材/主页皮肤.png`；上传走 `/upload_carousel`（name 白名单已含 `主页皮肤.png`），前端工具栏有「⬆ 主页皮肤背景」按钮。同样的 `load_override` 机制可扩展给 `卡片背景.png` / `评论气泡.png`
- **气泡底框五选一**: `气泡底框颜色`（`CAROUSEL_BUBBLE_PRESETS`）改为预置 5 色 `#FF8F56/#FEAD3A/#DEC84C/#A55DAB/#D04666`，前端渲染为圆点选择器（`.preset-swatch`），默认 `#FF8F56`；该颜色同时作用于 pic1.png 与评论气泡底色1/2
- **苹方字体必须打包**: GitHub Actions macOS 无 PingFang，需下载/预置 `fonts/PingFang.ttf`，用 `--add-data "fonts;fonts"` 打进包
- **Windows 打包素材路径**: 轮播素材必须用 `--add-data "原素材;原素材"`（打进 `_MEIPASS/原素材`），不要用 `../02/原素材;02/原素材`——frozen 后 `_get_carousel_dir()` 只找 `_MEIPASS/原素材`；字体也不能漏（`fonts;fonts`）
- **PIL paste 不带 mask**: `result.paste(p, (x, y))` 保持 alpha。`result.paste(img, pos, img)` 会稀释半透明像素
- **composite_scene**: 末尾强制 `arr[:,:,3]=255`
- **darken_overlay**: 阈值 alpha>200，半透明边缘不动
- **首次打开 Mac 包**: 右键 → 打开 → 仍要打开
