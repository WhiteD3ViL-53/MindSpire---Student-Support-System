#!/bin/bash
# launcher.sh (Updated)

set -e

# Start the Student App on internal port 8501
streamlit run mental.py --server.port 8501 --server.headless true &

# Start the Admin App on internal port 8502
# The --server.baseUrlPath is the crucial new part
streamlit run Admin.py --server.port 8502 --server.headless true --server.baseUrlPath admin &

# Start the Escalation Webhook on internal port 8000
python escalate.py &

# Start the Call Events Webhook on internal port 5001
python call_events.py &

# Start the Proxy server in the foreground
python proxy.py
