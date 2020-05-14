
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ShellCommandBase(CommandBase):
    """
    Usage:
        om shell [options]
    """
    command = 'shell'

    def shell(self):
        om = get_omega(self.args)
        use_ipython = False
        try:
            import IPython
        except:
            self.logger.warn("you should pip install ipython for convenience")
        else:
            use_ipython = True
        # ipython
        if use_ipython:
            IPython.embed(header='omegaml is available as the om variable', colors='neutral')
            return
        # default console
        import code
        try:
            import gnureadline
        except:
            self.logger.warn("you should pip install gnureadline for convenience")
        variables = {}
        variables.update(locals())
        shell = code.InteractiveConsole(locals=variables)
        shell.interact()
