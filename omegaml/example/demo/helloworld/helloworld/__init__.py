def hello(**kwargs):
    return "hello from helloworld", kwargs


def run(om, **kwargs):
    """
    the script API execution entry point
    :return: result
    """
    import pandas as pd
    df = pd.DataFrame({
        'a': list(range(0, int(1e6 + 1))),
        'b': list(range(0, int(1e6 + 1)))
    })
    store = om.datasets
    store.put(df, 'mydata-xlarge', append=False, chunksize=50000)
    result = hello(**kwargs)
    return result
