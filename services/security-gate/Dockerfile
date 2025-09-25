FROM python:3.12-slim

# libmagic for python-magic on Linux
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt.txt && \
    pip install --no-cache-dir --only-binary=:all: pikepdf

COPY . .
ENV UPLOAD_DIR=/data/uploads MAX_UPLOAD_MB=15 SERVICE_SECRET=dev-secret
EXPOSE 8001
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8001"]