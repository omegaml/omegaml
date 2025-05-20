from omegaml import settings
from omegaml.server.example import create_testdata
from omegaml.tests.util import clear_om

if __name__ == '__main__':
    import omegaml as om

    om._base_config.OMEGA_LOCAL_RUNTIME = True
    settings(reload=True)
    om = om.setup()
    clear_om(om)
    create_testdata(om)
