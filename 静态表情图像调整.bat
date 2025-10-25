@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo       静态表情图像调整工具
echo    1000x1000 -> 1024x1024 缩放
echo ========================================
echo.

REM 检查ImageMagick是否可用
magick -version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到ImageMagick，请确保已正确安装并添加到环境变量
    pause
    exit /b 1
)

REM 检查当前目录是否有图像文件
set "found=0"
for %%f in (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp) do (
    set "found=1"
    goto :process
)

if !found!==0 (
    echo 当前目录未找到支持的图像文件
    echo 支持的格式：jpg, jpeg, png, bmp, gif, tiff, webp
    pause
    exit /b 1
)

:process
echo 开始处理图像文件...
echo.

REM 创建输出目录
if not exist "resized" mkdir "resized"

set "count=0"
set "success=0"
set "failed=0"

REM 处理所有支持的图像格式
for %%f in (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp) do (
    set /a count+=1
    echo 正在处理: %%f
    
    REM 使用ImageMagick进行缩放，保持高质量
    magick "%%f" -resize 1024x1024! "resized\%%f" 2>nul
    
    if !errorlevel!==0 (
        set /a success+=1
        echo   ✓ 成功
    ) else (
        set /a failed+=1
        echo   ✗ 失败
    )
)

echo.
echo ========================================
echo 处理完成！
echo 总文件数: !count!
echo 成功: !success!
echo 失败: !failed!
echo 输出目录: resized\
echo ========================================

if !failed! gtr 0 (
    echo.
    echo 注意：有 !failed! 个文件处理失败，请检查文件格式或权限
)

pause