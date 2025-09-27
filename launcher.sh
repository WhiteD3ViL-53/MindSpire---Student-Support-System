#!/bin/bash
# launcher.sh (Final Version with Gunicorn)

set -e

# Start Student App on port 8501
streamlit run mental.py \
  --server.port 8501 \
  --server.headless true \
  --server.baseUrlPath student &

# Start Admin App on port 8502
streamlit run Admin.py \
  --server.port 8502 \
  --server.headless true \
  --server.baseUrlPath admin &

# Start the Escalation Webhook
python escalate.py &

# Start the Call Events Webhook
python call_events.py &

# Start the Proxy server in the foreground using a production server (Gunicorn)
# This is the crucial change that fixes the WebSocket issue.
gunicorn --bind "0.0.0.0:$PORT" --workers 1 --threads 4 --timeout 120 "proxy:app"
