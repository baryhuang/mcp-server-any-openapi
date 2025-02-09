# Use Python base image
FROM python:3.10-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install the project into `/app`
WORKDIR /app

# Copy the entire project
COPY . /app

# Install dependencies first for better caching
RUN pip install --no-cache-dir \
    mcp \
    pydantic \
    requests \
    "numpy<2.0" \
    fastapi \
    uvicorn \
    && pip install --no-cache-dir faiss-cpu sentence-transformers

# Install the package in development mode
RUN pip install -e .

# Run the server
ENTRYPOINT ["python", "-m", "mcp_server_any_openapi.server"]