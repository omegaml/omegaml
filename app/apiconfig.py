from app import settings
from tastypiex.centralize import ApiCentralizer
apis = ApiCentralizer(config=settings.API_CONFIG['apis'])