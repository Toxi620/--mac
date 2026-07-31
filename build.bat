@echo off
chcp 65001 >nul
echo === 0/6 检查编译环境 ===
pip show pillow >nul 2>&1 && pip show numpy >nul 2>&1 && pip show flask >nul 2>&1 && pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo   正在安装依赖...
    pip install pillow numpy flask pyinstaller
)

echo === 1/6 清理旧缓存 ===
rmdir /s /q build 2>nul
del 配色工具.spec 2>nul

echo === 写入构建版本 (commit) ===
git rev-parse --short HEAD > version.txt 2>nul
if errorlevel 1 echo dev> version.txt
for /f "delims=" %%i in (version.txt) do echo   版本: %%i

echo === 2/6 打包 ===
pyinstaller --onefile -w ^
  --distpath . ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "原素材;原素材" ^
  --add-data "fonts;fonts" ^
  --add-data "bg_0.png;." ^
  --add-data "bg_1.png;." ^
  --add-data "wz_0.png;." ^
  --add-data "lj_0.png;." ^
  --add-data "sk_0.png;." ^
  --add-data "left_.9.png;." ^
  --add-data "right_.9.png;." ^
  --add-data "wz_3.png;." ^
  --add-data "商城6字展示420X174.png;." ^
  --add-data "代码文档.docx;." ^
  --add-data "pipeline.py;." ^
  --add-data "version.txt;." ^
  --hidden-import numpy ^
  --name "配色工具" ^
  server.py

echo === 3/6 清理临时文件 ===
rmdir /s /q build 2>nul
del 配色工具.spec 2>nul
rmdir /s /q __pycache__ 2>nul

echo.
echo ✅ 全部完成！
echo 生成文件：配色工具.exe
echo 源码文件已保留，可重复运行 build.bat
