# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install uv for faster package management
RUN pip install --no-cache-dir uv

# Install Python dependencies
RUN uv pip install --system --no-cache \
    fastapi \
    uvicorn[standard] \
    pygithub \
    groq \
    httpx \
    python-dotenv

# Copy application code
COPY src/ ./src/

# Create /tmp directory for attachments and logs
RUN mkdir -p /tmp/tds_attachments /tmp/tds_storage

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV LOG_FILE_PATH=/tmp/tds_app.log

# Expose port 7860 (Hugging Face Spaces default)
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]
