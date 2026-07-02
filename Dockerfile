FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 180 "app:app"
