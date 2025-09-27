# webhook.py
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

@app.route("/voice", methods=["POST", "GET"])
def voice():
    """Basic TwiML for incoming calls: speaks then records a short message."""
    resp = VoiceResponse()
    resp.say("Hello. You have reached MindSpire demo. Please leave a message after the tone.", voice="alice")
    resp.record(max_length=30, play_beep=True, timeout=3)
    resp.hangup()
    return Response(str(resp), mimetype="text/xml")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
