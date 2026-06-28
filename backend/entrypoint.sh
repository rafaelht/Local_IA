#!/bin/bash

# Start the FastAPI server
echo "Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait for the server to be ready (give it 2 seconds)
sleep 2

# Export users to JSON file
echo "Exporting users to /app/export/users.json..."
cd /app
python -c "
import sys
sys.path.insert(0, '/app')
from app.db.export_users import export_users
try:
    export_users()
except Exception as e:
    print(f'Warning: Could not export users: {e}')
" || echo "⚠ Export skipped (database not ready yet)"

# Wait for the server process to continue running
wait
