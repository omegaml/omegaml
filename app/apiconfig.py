from app import settings
from tastypiex.centralize import ApiCentralizer
omega_apis = ApiCentralizer(config=getattr(settings, 'API_CONFIG')['omega_apis'],
                            path=r'^api/')
admin_apis = ApiCentralizer(config=getattr(settings, 'API_CONFIG')['admin_apis'],
                            path=r'^admin/api/')