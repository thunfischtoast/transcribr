FROM python:3.12-alpine

WORKDIR /app

# Install system dependencies
RUN apk add --no-cache \
    ffmpeg \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    jpeg-dev \
    zlib-dev

# Install Python dependencies
COPY frozen-requirements.txt .
RUN pip install --no-cache-dir --upgrade -r frozen-requirements.txt

# Create directories for data and uploads
RUN mkdir -p /app/data/uploads

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Health check
#HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
#    CMD curl -f http://localhost:8000/health || exit 1