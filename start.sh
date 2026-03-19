#!/bin/bash
cd ~/inventory-search
export PATH="/Users/hadikatranji/Library/Python/3.10/bin:$PATH"
set -a
source .env
set +a
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
