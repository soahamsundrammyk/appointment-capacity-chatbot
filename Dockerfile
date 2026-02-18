# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including libpq-dev for PostgreSQL)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    tzdata \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY capacity_chatbot/ ./capacity_chatbot/

# Install UV package manager for faster dependency installation
RUN pip install uv

# Install Python dependencies using uv
RUN uv pip install --system -e ".[dev]"

# Expose API port
EXPOSE 3334

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=3334
ENV MOUNT_PREFIX=/capacity-chatbot

# LangSmith tracing (always enabled)
ENV LANGCHAIN_TRACING_V2=true
ENV LANGCHAIN_PROJECT=capacity-chatbot

# Start FastAPI server with uvicorn
# Using custom API server for PostgreSQL persistence support
CMD ["uvicorn", "capacity_chatbot.api:app", "--host", "0.0.0.0", "--port", "3334"]

