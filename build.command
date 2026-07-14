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
ls fonts/PingFang.ttf 2>/dev/null && echo "  ✅ fonts/PingFang.ttf exists" || echo "  ⚠️ fonts/PingFang.ttf not found"

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