#!/bin/bash
# launcher.sh (Final Version)

set -e

# Start Student App on port 8501 with a specific base URL path
streamlit run mental.py \
  --server.port 8501 \
  --server.headless true \
  --server.baseUrlPath student &

# Start Admin App on port 8502 with its own base URL path
streamlit run Admin.py \
  --server.port 8502 \
  --server.headless true \
  --server.baseUrlPath admin &

# Start the Escalation Webhook
python escalate.py &

# Start the Call Events Webhook
python call_events.py &

# Start the Proxy server in the foreground
python proxy.py
