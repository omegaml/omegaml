def hello(**kwargs):
    return "hello from helloworld", kwargs


def run(om, **kwargs):
    """
    the script API execution entry point
    :return: result
    """
    result = hello(**kwargs)
    return result