#!/bin/sh
# 容器入口：等待数据库就绪 → 执行迁移 → 幂等初始化演示数据 → 启动服务
set -e

echo "[entrypoint] applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] seeding demo data (idempotent)..."
python manage.py bootstrap_demo || true

if [ "$ROLE" = "scheduler" ]; then
  echo "[entrypoint] running overdue scheduler, interval ${SCAN_INTERVAL_SECONDS:-600}s"
  while true; do
    python manage.py scan_overdue || true
    sleep "${SCAN_INTERVAL_SECONDS:-600}"
  done
fi

echo "[entrypoint] starting gunicorn..."
exec gunicorn app.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 60
