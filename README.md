# 配色工具 — macOS 自动打包

## 这是什么

微博预览图配色工具。输入色值，自动替换聊天气泡颜色、拉伸点九图、合成亮/暗双模式预览图，输出全套素材。

## 使用方法

### 方式一：网页版（推荐）
1. 到 **Actions** 页面 → 点 **"打包 Mac 版"** → **Run workflow**
2. 等 3-5 分钟
3. 下载 **Artifacts** 里的 `配色工具-Mac.zip`
4. 解压，首次打开 **右键 → 打开 → 仍要打开**

### 方式二：本地开发
```bash
pip3 install pillow numpy flask
python server.py
# 浏览器打开 http://localhost:5001
```

## 技术栈
- Python + Pillow + NumPy 图像处理
- Flask Web 服务
- PyInstaller 打包单文件
- GitHub Actions 自动编译（macOS arm64）

## 维护
改完代码直接推送 `main` 分支，Actions 会自动打包新版。
