FROM python:3.13-slim

RUN apt-get update && apt-get install -y git cron curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5001
HEALTHCHECK --interval=60s --timeout=10s CMD curl -f http://localhost:5001/api/health || exit 1

CMD ["python", "start.py"]
