from traitlets.config import Config

from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ShellCommandBase(CommandBase):
    """
    Usage:
        om shell [<command>] [options]

    Description:
        Without a command will start an IPython shell with omega|ml ready to use

        $ om shell
        [] om.runtime.ping()
        => { ... }

        By passing a command, run arbitrary Python code

        $ om shell "om.runtime.ping()"
    """
    command = 'shell'

    def shell(self):
        use_ipython = False
        command = self.args.get('<command>') or ''
        try:
            import IPython
        except:
            self.logger.warn("you should pip install ipython for convenience")
        else:
            use_ipython = True
        # ipython
        if use_ipython:
            c = Config()
            c.InteractiveShellApp.exec_lines = [
                'from omegaml.client.util import get_omega',
                'om = get_omega(shell_args)',
                'print("omegaml is available as the om variable")',
            ]
            c.TerminalIPythonApp.display_banner = False
            argv = f'-c {command}'.split(' ') if command else []
            IPython.start_ipython(argv,
                                  config=c, user_ns=dict(shell_args=self.args))
            return
        # default console
        import code
        om = get_omega(self.args)
        try:
            import gnureadline
        except:
            self.logger.warn("you should pip install gnureadline for convenience")
        variables = {}
        variables.update(locals())
        shell = code.InteractiveConsole(locals=variables)
        shell.interact()
