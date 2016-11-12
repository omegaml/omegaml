from __future__ import absolute_import
from omegaml.util import override_settings
override_settings(
    OMEGA_MONGO_URL='mongodb://localhost:27017/omegatest',
    OMEGA_MONGO_COLLECTION='store'
)