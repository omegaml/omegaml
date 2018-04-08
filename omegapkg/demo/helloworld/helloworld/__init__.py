def hello():
    print("hello from helloworld")


def run(*args, **kwargs):
    """
    the script API execution entry point
    :return: result
    """
    hello()
    return kwargs