from whitenoise.storage import CompressedManifestStaticFilesStorage


class FailsafeCompressedManifestStaticFilesStorage(
    CompressedManifestStaticFilesStorage):
    """
    originally from landingpage
    """
    def post_process(self, *args, **kwargs):
        """
        make the collectstatic command ignore exceptions
        """
        files = super(CompressedManifestStaticFilesStorage, self).post_process(*args, **kwargs)
        for name, hashed_name, processed in files:
            if isinstance(processed, Exception):
                processed = False
            yield name, hashed_name, processed
