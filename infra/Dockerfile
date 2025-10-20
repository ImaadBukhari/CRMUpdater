# === infra/Dockerfile ===
FROM python:3.12-slim

WORKDIR /app

# Copy backend code into container
COPY backend /app/backend

# Install dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

ENV PORT=8080
EXPOSE 8080

# Run FastAPI app (backend/main.py defines app)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
