# Algorithm Service

## Quick Start

### Local Dev

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Test algorithm directly
python main.py
```

### Run API Server

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:5001/docs for API documentation
```

### Docker

```bash
docker-compose up --build
# Open http://localhost:5001/docs
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check |
| /path | POST | Compute optimal path |