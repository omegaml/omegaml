from flask_restx import Resource, fields

from omegaml.backends.restapi.asyncrest import AsyncResponseMixin
from omegaml.server.restapi.util import AnyObject, OmegaResourceMixin


def create_api(api):
    TranscriptionsInput = api.model(
        'TranscriptionPayload',
        {
            'file': fields.Raw(required=True, dataType='file', doc="Upload an audio file (mp3, wav, mp4, etc.)"),
            'model': fields.String(
                default="whisper-1",
                enum=["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
                doc="Which Whisper model to use",
            ),
            'language': fields.String(default="auto", doc="Language code e.g. 'en', 'de' (optional)"),
            # FIXME is this supported?
            'prompt': fields.String(default="", doc="Optional prompt / context for the transcription"),
            'response_format': fields.String(
                default="json", enum=["json", "text", "srt", "verbose_json", "vtt"], doc="Format of the returned text"
            ),
            'streams': fields.Boolean(default=False, doc='response streaming'),
        },
    )

    # ── Success / error response schemas ────────────────────────────
    TranscriptionsOutput = api.model(
        'TranscriptionResult',
        {
            'text': fields.String(required=True, description="The transcribed text from the audio file."),
            'model': fields.String(description="Model used for transcription"),
            'resource_uri': fields.String(description='The resource URI'),
        },
    )

    TranscriptionsOutputGeneric = api.model('TranscriptionsOutputGeneric', {'*': AnyObject})

    TranscriptionsError = api.model(
        'ErrorResult',
        {
            'error': fields.String(required=True, description="Error message from OpenAI"),
        },
    )

    # ── Endpoint ────────────────────────────────────────────────────
    @api.route(
        '/api/openai/v1/audio/transcriptions',
        defaults={'action': 'transcribe', 'model_id': '_query_'},
        methods=['POST'],
        endpoint='openai_transcriptions',
    )
    class TranscriptionResource(OmegaResourceMixin, AsyncResponseMixin, Resource):
        doc = {
            "description": "Upload an audio file and receive its transcription.",
            "params": {
                'Authorization': 'Bearer token (optional, use env var instead)',
            },
            "responses": {
                200: ('Successful transcription', TranscriptionsOutput),
                400: ('Bad request - unsupported file or missing params', TranscriptionsError),
            },
        }

        @api.expect(TranscriptionsInput)
        @api.marshal_with(TranscriptionsOutputGeneric, code=200)
        @api.response(400, "File is not accepted")
        @api.response(503, "OpenAI service returned an error")
        def post(self, model_id, action=None):
            return self.create_response_from_resource('_generic_model_resource', action, 'model', model_id, raw=True)
