# --------
# Builder stage
# --------
FROM python:3.11-slim AS builder

# Install build tools and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libpq-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for builder
WORKDIR /app

# Copy the entire project first
COPY . /app/

# Upgrade pip and build wheels for all dependencies
RUN pip install --upgrade pip \
    && mkdir /wheels \
    && pip wheel --wheel-dir=/wheels -r requirements.txt

# --------
# Final runtime stage
# --------
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the entire project
COPY . /app/

# Copy the wheels built in the builder stage
COPY --from=builder /wheels /wheels

# Install Python dependencies from the local wheel cache
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Create models directory
RUN mkdir -p /app/models

# Pre-download models
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('all-MiniLM-L6-v2'); \
    model.save('/app/models/all-MiniLM-L6-v2')"

# Set environment variables
ENV SENTENCE_TRANSFORMERS_HOME=/app/models
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run the server directly
ENTRYPOINT ["python", "src/mcp_server_any_openapi/server.py"]
