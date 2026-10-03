FROM python:3.11-slim

WORKDIR /app

COPY requirements-hf.txt .
RUN pip install --no-cache-dir -r requirements-hf.txt

COPY app.py .
COPY templates ./templates

EXPOSE 7860

CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--timeout", "120", "app:app"]
