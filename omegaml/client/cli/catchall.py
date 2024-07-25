from importlib.metadata import metadata

from omegaml.client.docoptparser import CommandBase


class CatchallCommandBase(CommandBase):
    """
    Usage:
      om [--copyright]
    """
    command = "catchall"

    def __call__(self):
        if self.args.get('--copyright'):
            logger = self.logger
            logger.info("(c) omega|ml by one2seven GmbH, Zurich, Switzerland, https://omegaml.io")
            logger.info(f"licensed as {self.license}")
            logger.info("third party components (c) by their respective copyright holders")
            logger.info("see LICENSE and THIRDPARTY-LICENSES at https://github.com/omegaml/omegaml/")
            return
        self.parser.help()

    @property
    def license(self):
        package_metadata = metadata('omegaml')
        license_info = package_metadata.get("License")
        return license_info
