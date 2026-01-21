# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY langgraph.json ./

# Install UV package manager for faster dependency installation
RUN pip install uv

# Install Python dependencies using uv
RUN uv pip install --system -e ".[dev]"

# Install LangGraph CLI
RUN pip install "langgraph-cli[inmem]>=0.4.7"

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Expose LangGraph port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Start LangGraph server
# --no-browser prevents opening browser with 0.0.0.0 URL
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
