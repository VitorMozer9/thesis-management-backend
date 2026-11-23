FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUNICORN_CMD_ARGS=--no-control-socket

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt \
    && groupadd --gid 10001 thesis \
    && useradd --uid 10001 --gid thesis --no-create-home thesis \
    && install -d -m 0750 -o thesis -g thesis /var/lib/thesis/media

COPY config/ ./config/
COPY thesis/ ./thesis/
COPY manage.py ./
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "config.wsgi:application"]
