def run(om, payload, *args, **query):
    """
    the script API execution entry point
    :return: result
    """
    import pandas as pd
    factor = payload.get('factor')
    df = pd.DataFrame({
        'a': range(0, 5),
        'b': range(0, 5),
    })
    return (df * factor).to_dict(orient='list')
