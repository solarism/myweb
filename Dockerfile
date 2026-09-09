FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home webuser
COPY . .
RUN mkdir -p /data && chown webuser:webuser /data
USER webuser
ENV PORT=8000 DATABASE_PATH=/data/chat.sqlite3
EXPOSE 8000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 60 'app:create_app()'"]
