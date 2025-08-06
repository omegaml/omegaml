# app1.py
from flask import Flask, redirect, session, make_response
from uuid import uuid4

app = Flask(__name__)

@app.route('/chat/completions', methods=['POST'])
def complete():
    # Redirect to the second app's SSE endpoint
    session_id = uuid4().hex
    resp = make_response(redirect("http://localhost:5001/sse", code=302))
    resp.set_cookie('session_id', session_id, path='/sse', samesite='Strict')   
    app.logger.info("session: %s", session_id)
    return resp

if __name__ == '__main__':
    app.run(port=5002, debug=True)

