from django.test import TestCase


class OmegaEnterpriseTests(TestCase):
    def test_omegaee_imports(self):
        """
        test omegaml module setup uses enterprise implementation
        """
        # avoid circular imports
        import omegaml as om
        from omegaee.omega import EnterpriseOmegaDeferredInstance
        from omegaee.omega import EnterpriseOmega
        self.assertIsInstance(om._omega._om, EnterpriseOmegaDeferredInstance)
        self.assertTrue(om.Omega is EnterpriseOmega)
