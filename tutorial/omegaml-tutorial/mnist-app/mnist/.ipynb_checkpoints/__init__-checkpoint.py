# create_app must be importable from the package
# -- i.e. apphub will do this:
#    import mnist
#    server = mnist.create_app()
from .app import create_app