#!/usr/bin/env bash
# ============================================================
# Elasticsearch 8.17.1 + IK 中文分词插件 一键构建脚本
# 适用系统: Ubuntu 20.04+
# 用法: chmod +x build.sh && ./build.sh
# ============================================================
set -euo pipefail

ES_VERSION="8.17.1"
IMAGE_NAME="product-es-ik:${ES_VERSION}"
IK_ZIP="elasticsearch-analysis-ik-${ES_VERSION}.zip"
IK_DOWNLOAD_URL="https://release.infinilabs.com/analysis-ik/stable/${IK_ZIP}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="$SCRIPT_DIR/offline-packages"

echo "============================================"
echo " Elasticsearch ${ES_VERSION} + IK 分词器构建"
echo "============================================"
echo ""

# ---- 1. 检查 Docker ----
if ! command -v docker &> /dev/null; then
    echo "[ERROR] 未找到 Docker，请先安装 Docker"
    echo "        curl -fsSL https://get.docker.com | bash"
    exit 1
fi
echo "[OK] Docker 已安装: $(docker --version)"

# ---- 2. 检查/拉取 ES 基础镜像 ----
echo ""
echo "[1/4] 检查 ES 基础镜像..."
if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}"; then
    echo "  -> ES 基础镜像已存在，跳过拉取"
else
    echo "  -> 拉取 ES ${ES_VERSION} 基础镜像..."
    docker pull "docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}"
fi

# ---- 3. 下载 IK 插件 ----
echo ""
echo "[2/4] 下载 IK 分词器插件..."
mkdir -p "$PKG_DIR"
if [ -f "$PKG_DIR/$IK_ZIP" ]; then
    # 检查文件完整性 (至少 4MB)
    FILE_SIZE=$(stat -c%s "$PKG_DIR/$IK_ZIP" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -gt 4000000 ]; then
        echo "  -> ${IK_ZIP} 已存在 (${FILE_SIZE} bytes)，跳过下载"
    else
        echo "  -> 文件不完整，重新下载..."
        rm -f "$PKG_DIR/$IK_ZIP"
        curl -fSL --retry 3 --retry-delay 5 "$IK_DOWNLOAD_URL" -o "$PKG_DIR/$IK_ZIP"
    fi
else
    echo "  -> 从 ${IK_DOWNLOAD_URL} 下载..."
    curl -fSL --retry 3 --retry-delay 5 "$IK_DOWNLOAD_URL" -o "$PKG_DIR/$IK_ZIP"
fi

FILE_SIZE=$(stat -c%s "$PKG_DIR/$IK_ZIP" 2>/dev/null || echo 0)
echo "  -> offline-packages/${IK_ZIP} (${FILE_SIZE} bytes)"

# ---- 4. 构建镜像 ----
echo ""
echo "[3/4] 构建 ${IMAGE_NAME} ..."
docker build \
    -t "$IMAGE_NAME" \
    -f "$SCRIPT_DIR/Dockerfile" \
    "$SCRIPT_DIR"

# ---- 5. 验证 ----
echo ""
echo "[4/4] 验证 IK 插件..."
docker run --rm --entrypoint /bin/bash "$IMAGE_NAME" \
    -c "ls /usr/share/elasticsearch/plugins/ik/elasticsearch-analysis-ik-${ES_VERSION}.jar > /dev/null 2>&1 && echo '  -> IK 插件安装成功' || echo '  -> [ERROR] IK 插件未找到'" 2>&1

echo ""
echo "============================================"
echo " 构建完成！"
echo " 镜像: ${IMAGE_NAME}"
echo " 可用 docker-compose.yml 启动:"
echo "   docker compose up -d elasticsearch"
echo "============================================"
