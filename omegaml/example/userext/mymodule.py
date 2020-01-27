from omegaml.backends.basedata import BaseDataBackend


class MyBackend(BaseDataBackend):
    KIND = 'anything'

    @classmethod
    def supports(self, obj, name, **kwargs):
        print("Yeah, we support anything!")
        return True

