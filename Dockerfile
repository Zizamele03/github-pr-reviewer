# Multi-stage build for smaller final image
FROM python:3.10-slim as builder

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code (do not copy .env - use environment variables instead)
COPY src/ ./src/

# Create output directory for reviews
RUN mkdir -p reviews

# Set Python path
ENV PYTHONPATH=/app

# Default command - can be overridden with docker run
# Environment variables must be provided at runtime via -e or --env-file
CMD ["python", "-m", "src.main"]