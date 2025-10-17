FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/security_gate/requirements.txt /tmp/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 qpdf \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir --only-binary=:all: pikepdf

COPY . /app
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "services.security_gate.app:app", "--host", "0.0.0.0", "--port", "8000"]
