FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
ENV PIP_DEFAULT_TIMEOUT=180 PIP_RETRIES=10
RUN pip install --no-cache-dir --retries 10 -r /app/requirements.txt
COPY backend /app/backend
COPY frontend /app/frontend
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
