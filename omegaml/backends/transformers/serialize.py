import json
from pathlib import Path
from transformers import pipeline

from omegaml.util import infer_qualclass, load_class


class TransformersPipelineSerializer:
    """ a generic transformers.Pipeline serializer to safely save/reload huggingface transformer pipelines

    Saves and loads transformer pipelines by remembering the fully qualified names of all components. This
    is needed because pipeline.save_pretrained() while saving all components, doesn't recall their origin.

    Usage:
        text_pipe = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
        serializer = TransformersPipelineSerializer()
        serializer.save(text_pipe, '/path/to/dir')
        serializer.load('/path/to/dir')
    """

    def save(self, pipe, save_dir: str):
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        # save all components
        pipe.model.save_pretrained(save_dir)
        reload_kwargs = {
            'task': pipe.task,
            'model': infer_qualclass(pipe.model)
        }
        if hasattr(pipe, "tokenizer") and pipe.tokenizer is not None:
            pipe.tokenizer.save_pretrained(save_dir)
            reload_kwargs['tokenizer'] = infer_qualclass(pipe.tokenizer)
        if hasattr(pipe, "feature_extractor") and pipe.feature_extractor is not None:
            pipe.feature_extractor.save_pretrained(save_dir)
            reload_kwargs['feature_extractor'] = infer_qualclass(pipe.feature_extractor)
        if hasattr(pipe, "image_processor") and pipe.image_processor is not None:
            pipe.image_processor.save_pretrained(save_dir)
            reload_kwargs['image_processor'] = infer_qualclass(pipe.image_processor)
        with open(save_dir / 'loader_kwargs.json', 'w') as fout:
            json.dump(reload_kwargs, fout)
        return reload_kwargs

    def load(self, save_dir: str, **kwargs):
        save_dir = Path(save_dir)
        loader_kwargs = {}
        if (save_dir / 'loader_kwargs.json').exists():
            with open(save_dir / 'loader_kwargs.json', 'r') as fin:
                loader_kwargs = json.load(fin)
        loader_kwargs.update(kwargs)
        components = {}
        for kind, qualclass in loader_kwargs.items():
            if kind == 'task':
                continue
            KindType = load_class(qualclass)
            components[kind] = KindType.from_pretrained(save_dir)
        # create the pipeline with loaded components
        components.setdefault('device_map', 'auto')
        pipe = pipeline(
            task=loader_kwargs.get('task'),
            **components,
        )
        return pipe


# enable simplified use case by from .serialize import save, load
serializer = TransformersPipelineSerializer()
save = serializer.save
load = serializer.load
