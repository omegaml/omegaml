from app import settings
from tastypiex.centralize import ApiCentralizer
apis = ApiCentralizer(config=getattr(settings, 'API_CONFIG')['apis'])