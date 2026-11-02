FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FANTA_DATA_DIR=/app/data \
    FANTA_HOST=0.0.0.0 \
    FANTA_PORT=27845

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY storage.py app.py ./
COPY templates ./templates

RUN mkdir -p /app/data

EXPOSE 27845

CMD ["gunicorn", "--bind", "0.0.0.0:27845", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]

