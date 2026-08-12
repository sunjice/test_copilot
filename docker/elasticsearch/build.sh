#!/usr/bin/env bash
# ============================================================
# Elasticsearch 8.17.1 + IK 中文分词插件 构建脚本
# 用法: chmod +x build.sh && ./build.sh
# ============================================================
set -euo pipefail

IMAGE_NAME="tc-es-ik:8.17.1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo " Elasticsearch 8.17.1 + IK 分词器构建"
echo "============================================"
echo ""

echo "[1/2] 构建镜像 ${IMAGE_NAME} ..."
docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile" "$SCRIPT_DIR"

echo ""
echo "[2/2] 验证 IK 插件..."
docker run --rm --entrypoint /bin/bash "$IMAGE_NAME" \
    -c "ls /usr/share/elasticsearch/plugins/ik/elasticsearch-analysis-ik-8.17.1.jar > /dev/null 2>&1 && echo '  IK 插件安装成功' || echo '  [ERROR] IK 插件未找到'"

echo ""
echo "============================================"
echo " 构建完成！镜像: ${IMAGE_NAME}"
echo "============================================"
