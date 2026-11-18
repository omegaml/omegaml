import unittest
from base64 import b64encode
from pathlib import Path
from unittest import mock, skip

import omegaml
from omegaml.backends.genai.modality.multicontent import binary_to_openai_content, extract_base64, guess_type
from omegaml.backends.genai.models import ConversationModel
from omegaml.client.util import dotable, subdict
from omegaml.tests.util import OmegaTestMixin


class MultimodalityTestCase(OmegaTestMixin, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @mock.patch('omegaml.backends.genai.providers.OpenAIProvider')
    def test_transcription(self, OpenAIProvider):
        om = self.om
        meta = self.om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        model: ConversationModel = self.om.models.get('mymodel', data_store=self.om.datasets)
        model.provider = OpenAIProvider
        model.provider.transcribe.side_effect = lambda audio_path, *args, **kwargs: dotable(
            {"text": "Hello world, what have you become?"},
        )
        # model.base_url = 'http://neptun:13305/v1'
        base_path = Path(omegaml.__file__).parent / 'example/demo/multimodal/resources'
        resp = model.transcribe(base_path / 'sample.wav', response_format='json')
        model.provider.transcribe.assert_called()
        self.assertEqual(
            resp,
            {
                'text': 'Hello world, what have you become?',
                'format': 'json',
            },
        )
        # use a dataset as input
        with open(base_path / 'sample.wav', 'rb') as fin:
            sample_meta = om.datasets.put(fin, 'sample.wav')
        resp = model.transcribe('sample.wav', response_format='json')
        model.provider.transcribe.assert_called()
        self.assertEqual(
            subdict(resp, ['text']),
            {'text': 'Hello world, what have you become?'},
        )

    def test_extract_b64data(self):
        wav_file_path = Path(omegaml.__file__).parent / 'example/demo/multimodal/resources/sample.wav'
        with open(wav_file_path, 'rb') as fin:
            audio_bytes = fin.read()
        audio_bytes_b64 = b64encode(audio_bytes)
        audio_bytes_data = binary_to_openai_content(audio_bytes)['content'][0]['input_audio']['data']
        audio_bytes_url = f"data:audio/mpeg;base64,{audio_bytes_b64.decode('utf-8')}"
        self.assertEqual(extract_base64(audio_bytes_b64), audio_bytes)
        self.assertEqual(extract_base64(audio_bytes_data), audio_bytes)
        self.assertEqual(extract_base64(audio_bytes_url), audio_bytes)

    @skip('TODO mock remote path')
    def test_speech(self):
        om = self.om
        meta = self.om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        model: ConversationModel = self.om.models.get('mymodel', data_store=self.om.datasets)
        model.base_url = 'http://neptun:13305/v1'
        # return audio file
        resp = model.speech('hello world', response_format='wav')
        self.assertEqual(guess_type(resp), 'audio/wav')
        # save to local file
        resp = model.speech('hello world', output_path='/tmp/test_speech.wav', response_format='wav')
        self.assertEqual(guess_type(resp), 'audio/wav')
        self.assertTrue(Path(resp).is_file and Path(resp).exists())
        # save to dataset
        resp = model.speech('hello world', data_store=om.datasets, dataset='foo')
        self.assertIsInstance(resp, om.datasets._Metadata)
        contents = om.datasets.get('foo').read()
        self.assertEqual(guess_type(contents), 'audio/wav')


if __name__ == '__main__':
    unittest.main()
