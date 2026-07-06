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

echo === 2/6 打包 ===
pyinstaller --onefile --console ^
  --distpath . ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
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
  --hidden-import numpy ^
  --name "配色工具" ^
  server.py

echo === 3/6 清理临时文件 ===
rmdir /s /q build 2>nul
del 配色工具.spec 2>nul
rmdir /s /q __pycache__ 2>nul

echo === 4/6 清理打包素材 ===
rmdir /s /q templates 2>nul
rmdir /s /q static 2>nul
del bg_0.png bg_1.png wz_0.png lj_0.png sk_0.png left_.9.png right_.9.png wz_3.png 2>nul
del 商城6字展示420X174.png 2>nul
del pipeline.py server.py 代码文档.docx 2>nul

echo.
echo ✅ 全部完成！
echo 生成文件：配色工具.exe
