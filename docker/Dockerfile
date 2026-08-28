# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx-extras \
    mosquitto \
    supervisor \
    python3 \
    python3-pip \
    python3-venv \
    git \
    ca-certificates \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY debian/changelog /app/debian/changelog
COPY backend/requirements.txt backend/setup.py backend/wb-homeui-backend backend/wb-terminal-server ./
COPY backend/wb ./wb
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
    && pip3 install --no-cache-dir --break-system-packages -e .

RUN install -m 0755 wb-homeui-backend /usr/local/bin/wb-homeui-backend \
    && install -m 0755 wb-terminal-server /usr/local/bin/wb-terminal-server

COPY --from=frontend-build /app/frontend/dist /var/www

RUN mkdir -p \
    /usr/share/wb-mqtt-homeui/mosquitto/acl \
    /usr/share/wb-mqtt-homeui/nginx/includes \
    /etc/nginx/includes/default.wb.d \
    /var/lib/wb-homeui/nginx-gates

COPY backend/webui-configs/config.default.json backend/webui-configs/config.wb5.json \
    /usr/share/wb-mqtt-homeui/
COPY backend/configs/usr/share/wb-mqtt-homeui/mosquitto/acl/ \
    /usr/share/wb-mqtt-homeui/mosquitto/acl/

COPY docker/nginx/default.docker.conf /etc/nginx/sites-enabled/homeui.conf
COPY docker/nginx/listen.conf /etc/nginx/includes/default.wb.d/listen.conf
RUN rm -f /etc/nginx/sites-enabled/default

COPY docker/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf
RUN rm -f /etc/mosquitto/conf.d/*
COPY docker/mosquitto/homeui-listeners.conf /etc/mosquitto/conf.d/homeui-listeners.conf

COPY docker/ /docker/
RUN chmod +x /docker/entrypoint.sh /docker/stubs/wb-gen-serial /docker/stubs/systemctl

EXPOSE 80
ENTRYPOINT ["/docker/entrypoint.sh"]
