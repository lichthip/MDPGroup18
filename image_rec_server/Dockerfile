FROM python:3.11-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (uncomment if needed for OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxrandr2 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (including uvicorn)
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application
COPY . /app

EXPOSE 8000

# Use uvicorn directly for better performance and configuration
CMD ["uvicorn", "inference_server:app", "--host", "0.0.0.0", "--port", "8000"]
