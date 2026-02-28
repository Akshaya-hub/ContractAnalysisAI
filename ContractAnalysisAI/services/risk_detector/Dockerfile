FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/risk_detector/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
ENV PYTHONPATH=/app
EXPOSE 8003
CMD ["uvicorn", "services.risk_detector.app:app", "--host", "0.0.0.0", "--port", "8003"]
