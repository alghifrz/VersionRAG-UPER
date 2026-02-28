FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (kept minimal). Add more only if a wheel requires it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt /app/requirements.txt
COPY src/requirements.txt /app/src/requirements.txt
COPY src/interface/requirements.txt /app/src/interface/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Railway provides $PORT
ENV PORT=8000
EXPOSE 8000

CMD ["python", "src/interface/backend/app.py"]


