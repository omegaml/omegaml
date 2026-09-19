import logging

import openai
from flask import Flask
from flask_restx import Api, Resource, fields

from omegaml.backends.restapi.asyncrest import AsyncResponseMixin
from omegaml.server.restapi.util import AnyObject, OmegaResourceMixin

app = Flask(__name__)
api = Api(app, version='1.0', title='Audio Speech API', description='OpenAI-compatible text-to-speech API', doc='/docs')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set your OpenAI API key
openai.api_key = "your-api-key-here"

# Create namespace
ns = api.namespace('audio', description='Audio operations')


def create_api(api):
    # Define request model for validation
    SpeechInput = api.model(
        'SpeechInput',
        {
            'model': fields.String(required=True, description='Model to use (e.g., tts-1, tts-1-hd)', example='tts-1'),
            'input': fields.String(required=True, description='Text to convert to speech', example='Hello world'),
            'voice': fields.String(
                required=True,
                description='Voice to use (alloy, echo, fable, onyx, nova, shimmer)',
                enum=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
                example='alloy',
            ),
            'response_format': fields.String(
                required=False,
                description='Output format (mp3, opus, aac, flac, wav, pcm)',
                enum=['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'],
                default='mp3',
                example='mp3',
            ),
            'speed': fields.Float(
                required=False, description='Speed of speech (0.25 to 4.0)', default=1.0, example=1.0
            ),
        },
    )

    SpeechOutputGeneric = api.model('SpeechOutputGeneric', {'*': AnyObject})

    @api.route(
        '/api/openai/v1/audio/speech',
        defaults={'action': 'speech', 'model_id': '_query_'},
        methods=['POST'],
        endpoint='openai_speech',
    )
    class AudioSpeech(OmegaResourceMixin, AsyncResponseMixin, Resource):
        @api.doc('synthesize speech from text')
        @api.expect(SpeechInput)
        # @api.marshal_with(SpeechOutputGeneric, code=200)
        @ns.response(200, 'Audio file generated successfully')
        @ns.response(400, 'Invalid request parameters')
        def post(self, model_id, action=None):
            """
            Generate speech from text using OpenAI TTS API.

            Returns the audio file in the requested format.
            """
            return self.create_response_from_resource('_generic_model_resource', action, 'model', model_id, raw=True)
