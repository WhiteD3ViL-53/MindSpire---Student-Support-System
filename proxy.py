# proxy.py — simple HTTP proxy to forward / and /admin paths to local services.
# NOTE: Use for local development or special multi-process containers only.
import os
import requests
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)

MAIN_TARGET = os.environ.get("MAIN_TARGET", "http://127.0.0.1:8501")
ADMIN_TARGET = os.environ.get("ADMIN_TARGET", "http://127.0.0.1:8502")
PORT = int(os.environ.get("PORT", 8080))

def _proxy_request(target_base):
    # request.full_path contains path + query (e.g. /path?x=1). Remove trailing ? if no query.
    path = request.full_path
    if path.endswith('?'):
        path = path[:-1]
    target_url = target_base + path

    # Build headers — skip hop-by-hop headers and Host
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")}

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
    except Exception as e:
        return Response(f"Upstream request failed: {e}", status=502)

    excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    resp_headers = [(n, v) for n, v in resp.headers.items() if n.lower() not in excluded]

    return Response(
        stream_with_context(resp.iter_content(chunk_size=8192)),
        status=resp.status_code,
        headers=resp_headers,
    )

# Admin proxy
@app.route("/admin", defaults={"path": ""}, methods=["GET","POST","OPTIONS","PUT","DELETE","PATCH"])
@app.route("/admin/<path:path>", methods=["GET","POST","OPTIONS","PUT","DELETE","PATCH"])
def proxy_admin(path):
    return _proxy_request(ADMIN_TARGET)

# Main proxy
@app.route("/", defaults={"path": ""}, methods=["GET","POST","OPTIONS","PUT","DELETE","PATCH"])
@app.route("/<path:path>", methods=["GET","POST","OPTIONS","PUT","DELETE","PATCH"])
def proxy_main(path):
    return _proxy_request(MAIN_TARGET)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
