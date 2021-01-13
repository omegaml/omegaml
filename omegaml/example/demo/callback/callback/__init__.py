import numpy as np

def run(om, *args, state=None, results=None, **kwargs):
    """
    the script API execution entry point
    :return: result
    """
    for result in results:
        if isinstance(result, np.ndarray):
            om.datasets.put(result, 'callback_results', as_pydata=True)
    return state
