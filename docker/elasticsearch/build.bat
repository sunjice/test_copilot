@echo off
setlocal
:: ============================================================
:: Elasticsearch 8.17.1 + IK 中文分词插件 构建脚本
:: 用法: 双击运行 或 build.bat
:: ============================================================

set IMAGE_NAME=tc-es-ik:8.17.1
set SCRIPT_DIR=%~dp0

echo ============================================
echo  Elasticsearch 8.17.1 + IK 分词器构建
echo ============================================
echo.

echo [1/2] 构建镜像 %IMAGE_NAME% ...
docker build -t "%IMAGE_NAME%" -f "%SCRIPT_DIR%Dockerfile" "%SCRIPT_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] 镜像构建失败
    pause
    exit /b 1
)

echo.
echo [2/2] 验证 IK 插件...
docker run --rm --entrypoint /bin/bash "%IMAGE_NAME%" -c "ls /usr/share/elasticsearch/plugins/ik/elasticsearch-analysis-ik-8.17.1.jar > nul 2>&1 && echo   IK 插件安装成功 || echo   [ERROR] IK 插件未找到"

echo.
echo ============================================
echo  构建完成！镜像: %IMAGE_NAME%
echo ============================================
pause
