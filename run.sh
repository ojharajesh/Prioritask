#!/bin/bash
# Runner script for Prioritask To-Do Web Application
PORT=3000
HOST="0.0.0.0"
echo "Starting Prioritask on http://${HOST}:${PORT} ..."
echo "Local access: http://127.0.0.1:${PORT}"
echo "Network / iPhone access: http://$(ipconfig getifaddr en0 || echo 'YOUR_MAC_IP'):${PORT}"
exec python3 -m uvicorn todo_app.server:app --host ${HOST} --port ${PORT}

