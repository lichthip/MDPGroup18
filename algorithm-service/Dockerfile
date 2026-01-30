FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY api/ ./api/

# Expose port
EXPOSE 5001

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "5001"]
