FROM python:3.12-slim

WORKDIR /app

# Install system dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories for persistent data
RUN mkdir -p /app/data/telegram_session /app/data/db

# Expose port 8082
EXPOSE 8082

# Run in interactive mode
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"] 
