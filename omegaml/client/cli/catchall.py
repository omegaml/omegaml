from importlib.metadata import metadata

from omegaml.client.docoptparser import CommandBase


class CatchallCommandBase(CommandBase):
    """
    Usage:
        om [--copyright]
    """
    command = "catchall"

    def parse(self):
        if self.parser.args.get('--copyright'):
            console = self.console
            console.print("(c) omega-ml by one2seven GmbH, Zurich, Switzerland, https://omegaml.io")
            console.print(f"licensed as {self.license}")
            console.print("third party components (c) by their respective copyright holders")
            console.print("see LICENSE and THIRDPARTY-LICENSES at https://github.com/omegaml/omegaml/")
            raise SystemExit(0)

    def help(self, usage_only=False):
        # this is a catchall command, so we show the main help instead of our own
        self.parser.help()

    @property
    def license(self):
        package_metadata = metadata('omegaml')
        license_info = package_metadata.get("License")
        return license_info
