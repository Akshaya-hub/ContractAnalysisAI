FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/orchestrator/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
	&& pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
ENV PYTHONPATH=/app
EXPOSE 8008
CMD ["uvicorn", "services.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8008"]
