FROM python:3.12-slim

WORKDIR /app

# 先複製 requirements 避免層快取失效
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
