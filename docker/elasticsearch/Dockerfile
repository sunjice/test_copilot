FROM docker.elastic.co/elasticsearch/elasticsearch:8.17.1

# Install IK Analysis plugin (离线 — zip 放在 offline-packages/ 目录)
COPY offline-packages/elasticsearch-analysis-ik-8.17.1.zip /tmp/elasticsearch-analysis-ik-8.17.1.zip
RUN mkdir -p /usr/share/elasticsearch/plugins/ik \
    && unzip -q /tmp/elasticsearch-analysis-ik-8.17.1.zip -d /usr/share/elasticsearch/plugins/ik \
    && chown -R elasticsearch:root /usr/share/elasticsearch/plugins/ik
