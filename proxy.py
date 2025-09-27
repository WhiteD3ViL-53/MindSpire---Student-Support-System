# proxy.py (Final Version)
import os
import requests
from flask import Flask, request, Response, stream_with_context, redirect

app = Flask(__name__)

# --- Internal targets for each service running in the container ---
TARGETS = {
    "student": os.environ.get("STUDENT_TARGET", "http://127.0.0.1:8501"),
    "admin": os.environ.get("ADMIN_TARGET", "http://127.0.0.1:8502"),
    "escalate": os.environ.get("ESCALATE_TARGET", "http://127.0.0.1:8000"),
    "call_events": os.environ.get("CALLEVENTS_TARGET", "http://127.0.0.1:5001")
}

PORT = int(os.environ.get("PORT", 8080))

def _proxy_request(target_base_url):
    """Streams the request and response, correctly passing headers."""
    target_url = target_base_url + request.full_path
    
    # Correctly pass along the Host header
    headers = {key: value for (key, value) in request.headers}
    headers['Host'] = request.host.split(':')[0] # Use the public host, not the internal one

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            stream=True,
            timeout=30
        )
    except requests.exceptions.RequestException as e:
        return Response(f"Upstream service failed: {e}", status=502)

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    resp_headers = [(name, value) for name, value in resp.raw.headers.items() if name.lower() not in excluded_headers]

    return Response(stream_with_context(resp.iter_content(chunk_size=8192)), resp.status_code, resp_headers)

# --- Routing rules ---
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy_router(path):
    """Directs traffic based on the URL path."""
    if path.startswith("admin"):
        return _proxy_request(TARGETS["admin"])
    if path.startswith("escalate"):
        return _proxy_request(TARGETS["escalate"])
    if path.startswith("call-events"):
        return _proxy_request(TARGETS["call_events"])
    
    # All other paths, including /student, go to the student app
    return _proxy_request(TARGETS["student"])

@app.route("/")
def index():
    """Redirects the root path to the student app."""
    return redirect("/student/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
