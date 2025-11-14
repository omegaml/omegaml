import dill
import torch

from omegaml.backends.basemodel import BaseModelBackend


class PytorchModelBackend(BaseModelBackend):
    """ Backend to store pytorch models

    Saves pytorch models using the generic torch.save() and torch.load() methods.
    For other torch saving and loading methods, use a helper virtualobj.

    See Also:
        - https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html
    """
    KIND = 'pytorch.pth'

    serializer = lambda store, model, filename, **kwargs: torch.save(model, filename, pickle_module=dill)
    loader = lambda store, infile, filename=None, **kwargs: torch.load(infile, pickle_module=dill, weights_only=False)
    types = torch.nn.Module
    infer = lambda obj, **kwargs: obj
    reshape = lambda data, **kwargs: torch.tensor(data)
