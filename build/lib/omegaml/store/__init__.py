from __future__ import absolute_import
from .base import OmegaStore
from .query import MongoQ, Filter
from .queryops import MongoQueryOps, GeoJSON
  
qops = MongoQueryOps()