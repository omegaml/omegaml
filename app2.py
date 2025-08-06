# app2.py
import json
from time import sleep

from flask import Flask, Response, request, abort

app = Flask(__name__)

# Sample words to send in the SSE stream
words = [f"word{i}" for i in range(1, 10)]


def generate_sse():
    for word in words:
        message = json.dumps({'choices': [{'delta': {'content': str(word), 'stop_reason': None}}]})
        yield f"data: {message}\n\n"
        sleep(0.1)  # Simulate delay for streaming


@app.route('/sse', methods=['GET', 'POST'])
async def sse():
    session_id = request.cookies.get('session_id')
    app.logger.info('session: %s', session_id)
    if not session_id:
        abort(401)
    return Response(generate_sse(), content_type='text/event-stream')


if __name__ == '__main__':
    app.run(port=5001, threaded=True, debug=True)
