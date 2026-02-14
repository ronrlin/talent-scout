FROM python:3.11-slim-bookworm

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application code
COPY . .

# Create directories and install
RUN mkdir -p data output input && \
    pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
