import dj_database_url
import os

from stackable import StackableSettings


def fix_mssql(settings, **kwargs):
    # neither dj-database-url nor django-environ support django-mssql
    # https://github.com/microsoft/mssql-django
    # https://github.com/jazzband/dj-database-url/issues/149
    # https://github.com/joke2k/django-environ/issues/295
    settings['DATABASES']['default']['ENGINE'] = 'mssql'


class Config_DatabaseUrl:
    """ configure DATABASES from DATABASE_URL

    This transparently provides support for specifying the settings.DATABASES
    for multiple types of DATABASE_URL.

    Rationale:
        The rationale for doing it using a Config class instead of
        directly using dj_database_url.config() is to easily handle
        database specifics, like for mssql.

    See Also:
        - https://github.com/jazzband/dj-database-url#url-schema
    """
    DATABASES = {
        'default': dj_database_url.config(default='sqlite://db.sqlite3'),
    }
    # https://github.com/microsoft/mssql-django
    if 'mssql' in os.environ.get('DATABASE_URL', ''):
        StackableSettings.patch(fix_mssql)


