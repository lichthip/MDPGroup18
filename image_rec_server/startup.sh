#!/bin/bash
source .venv/bin/activate
uvicorn inference_server:app --host 127.0.0.1 --port 8000