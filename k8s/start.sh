#!/bin/bash
set -e

# Start uvicorn backend in the background
echo "Starting uvicorn backend on port $PORT..."
uvicorn ai_blogger.frontend_api:app --host 127.0.0.1 --port ${PORT:-8000} &

# Wait a moment for backend to start
sleep 2

# Start nginx in the foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"
