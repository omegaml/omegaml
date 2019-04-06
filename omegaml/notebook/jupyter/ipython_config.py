# http://ipython.readthedocs.io/en/5.x/config/intro.html#profiles
# http://ipython.readthedocs.io/en/5.x/config/intro.html#example-config-file
# note in the link above it says "you can also keep a profile in the
# current working directory". so put this file in the cwd and it will actually
# execute on kernel starts

c = get_config()

c.InteractiveShellApp.exec_files = [
    'ipystart.py'
]
print("omegaml: ipython initialized from {}".format(__file__))
