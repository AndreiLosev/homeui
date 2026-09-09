#!/bin/bash
set -euo pipefail

mkdir -p \
  /run/mosquitto \
  /tmp \
  /var/lib/wirenboard/db \
  /var/lib/wb-homeui/fonts \
  /var/lib/wb-homeui/nginx \
  /var/lib/wb-homeui/nginx-gates \
  /var/lib/wb-homeui/custom-menu \
  /var/cache/nginx/wb-gate-auth \
  /var/www/uploads \
  /etc/nginx/includes/default.wb.d \
  /usr/share/wb-mqtt-homeui/nginx/includes

chown mosquitto:mosquitto /run/mosquitto

if [ ! -f /etc/wb-webui.conf ]; then
  cp /usr/share/wb-mqtt-homeui/config.default.json /etc/wb-webui.conf
fi

if [ ! -f /etc/wb-homeui-backend.conf ]; then
  echo '{"enable_https": false}' > /etc/wb-homeui-backend.conf
fi

install -m 0755 /docker/stubs/wb-gen-serial /usr/local/bin/wb-gen-serial
install -m 0755 /docker/stubs/systemctl /usr/local/bin/systemctl
install -m 0755 /docker/stubs/systemctl /usr/bin/systemctl
install -m 0644 /docker/stubs/wb-release /usr/lib/wb-release

exec /usr/bin/supervisord -c /docker/supervisord.conf
