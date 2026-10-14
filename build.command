#!/bin/bash
# ═══════════════════════════════════════
# 配色工具 — macOS 打包脚本
# 用法：双击运行，或在终端 bash build.command
# ═══════════════════════════════════════

# 切换到脚本自己所在的目录
cd "$(dirname "$0")"

set -e

echo "=== 0/6 检查编译环境 ==="
MISSING=""
for pkg in pillow numpy flask pyinstaller; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done
if [ -n "$MISSING" ]; then
    echo "⚠️  缺少依赖:$MISSING"
    echo "   正在安装..."
    pip3 install --break-system-packages $MISSING
    echo "✅ 安装完成"
else
    echo "✅ 所有依赖已就绪"
fi

echo "=== 1/6 复制系统字体 ==="
mkdir -p fonts
for f in PingFang.ttf NotoSansSC-Light.ttf NotoSans-Light.ttf Roboto-Regular.ttf; do
  if [ -f "fonts/$f" ]; then echo "  ✅ fonts/$f"; else echo "  ⚠️ fonts/$f 缺失（对应字体链会回退）"; fi
done

echo "=== 写入构建版本 (commit) ==="
git rev-parse --short HEAD > version.txt 2>/dev/null || echo "dev" > version.txt
echo "  版本: $(cat version.txt)"

echo "=== 获取 ffmpeg (mac 静态二进制，gif 动效用) ==="
FFMPEG_URL="https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip"
FFPROBE_URL="https://evermeet.cx/ffmpeg/ffprobe-7.1.zip"
mkdir -p /tmp/ffmpeg-bundle
# 镜像（deolaha.ca）会限流：HTTP 200 但 body 是 "429 Too Many Connections"（24字节），
# curl 视作成功、unzip 必炸 —— 所以下载后必须实跑 -version 验证，不行就重试
fetch_bin() {
    # $1=url $2=zip路径 $3=二进制名(ffmpeg/ffprobe)
    local url="$1" zip="$2" name="$3" i
    for i in 1 2 3; do
        echo "  下载 $name (第 $i 次)..."
        curl -L --connect-timeout 20 -o "$zip" "$url" || { sleep 15; continue; }
        unzip -o "$zip" -d /tmp/ffmpeg-bundle/ || { sleep 15; continue; }
        chmod +x "/tmp/ffmpeg-bundle/$name"
        if "/tmp/ffmpeg-bundle/$name" -version >/dev/null 2>&1; then
            return 0
        fi
        rm -f "/tmp/ffmpeg-bundle/$name"
        sleep 15
    done
    return 1
}
fetch_bin "$FFMPEG_URL" /tmp/ffmpeg.zip ffmpeg || true
fetch_bin "$FFPROBE_URL" /tmp/ffprobe.zip ffprobe || true
# 兜底：镜像被限流时改用 Homebrew 的 ffmpeg/ffprobe（慢几分钟但稳）
if [ ! -x /tmp/ffmpeg-bundle/ffmpeg ] || [ ! -x /tmp/ffmpeg-bundle/ffprobe ]; then
    echo "  镜像下载失败，改用 Homebrew ffmpeg..."
    brew install ffmpeg
    cp "$(brew --prefix)/bin/ffmpeg" "$(brew --prefix)/bin/ffprobe" /tmp/ffmpeg-bundle/
fi
chmod +x /tmp/ffmpeg-bundle/ffmpeg /tmp/ffmpeg-bundle/ffprobe
echo "  ffmpeg: $(/tmp/ffmpeg-bundle/ffmpeg -version 2>&1 | head -1)"

echo "=== 2/6 清理旧缓存 ==="
rm -rf build/ 配色工具.spec

echo "=== 3/6 打包 ==="
python3 -m PyInstaller --onefile \
  --distpath . \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --add-data "原素材:原素材" \
  --add-data "fonts:fonts" \
  --add-data "bg_0.png:." \
  --add-data "bg_1.png:." \
  --add-data "wz_0.png:." \
  --add-data "lj_0.png:." \
  --add-data "sk_0.png:." \
  --add-data "left_.9.png:." \
  --add-data "right_.9.png:." \
  --add-data "wz_3.png:." \
  --add-data "商城6字展示420X174.png:." \
  --add-data "代码文档.docx:." \
  --add-data "pipeline.py:." \
  --add-data "version.txt:." \
  --add-binary "/tmp/ffmpeg-bundle/ffmpeg:." \
  --add-binary "/tmp/ffmpeg-bundle/ffprobe:." \
  --hidden-import numpy \
  --name "配色工具" \
  server.py

echo "=== 3/6 签名 ==="
codesign --force --deep --sign - 配色工具

echo "=== 4/6 清理临时文件 ==="
rm -rf build/ __pycache__ 配色工具.spec

echo "=== 6/6 清理打包素材（已打进包里的） ==="
rm -rf templates/ static/ fonts/
rm -f bg_0.png bg_1.png wz_0.png lj_0.png sk_0.png left_.9.png right_.9.png wz_3.png 商城6字展示420X174.png
rm -f pipeline.py server.py 代码文档.docx

echo ""
echo "✅ 全部完成！"
echo "生成文件：配色工具"
echo ""
echo "剩余文件（可直接压缩发送）："
ls -lh
echo ""
echo "把这个文件发给别人，首次打开记得："
echo "  右键 配色工具 → 打开 → 仍要打开"