#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Start the Student App (mental.py) on an internal port
streamlit run mental.py --server.port 8501 --server.headless true &

# Start the Admin App (Admin.py) on another internal port
streamlit run Admin.py --server.port 8502 --server.headless true &

# Start the Escalation Webhook (escalate.py) on its port
python escalate.py &

# Start the Call Events Webhook (call_events.py) on its port
python call_events.py &

# Start the Proxy server in the foreground. This is the main process that will
# accept public traffic and keep the container running.
python proxy.py
