from django.core.exceptions import ImproperlyConfigured
from django.db import NotSupportedError
from libsql.db.backends.sqlite3.base import DatabaseWrapper as LibsqlDatabaseWrapper
import turso_serverless

from .driver import TursoCursorWrapper


class DatabaseWrapper(LibsqlDatabaseWrapper):
    Database = turso_serverless

    def get_connection_params(self):
        settings_dict = self.settings_dict
        if not settings_dict["NAME"]:
            raise ImproperlyConfigured(
                "The Turso database URL must be set in DATABASES['default']['NAME']."
            )

        options = settings_dict["OPTIONS"]
        auth_token = options.get("auth_token")
        if not auth_token:
            raise ImproperlyConfigured(
                "Set TURSO_AUTH_TOKEN to connect to the Turso database."
            )

        unsupported_options = set(options) - {"auth_token", "isolation_level"}
        if unsupported_options:
            names = ", ".join(sorted(unsupported_options))
            raise ImproperlyConfigured(
                f"Unsupported Turso database option(s): {names}."
            )

        return {
            "database": settings_dict["NAME"],
            "auth_token": auth_token,
            "isolation_level": options.get("isolation_level", ""),
        }

    def get_new_connection(self, conn_params):
        params = conn_params.copy()
        url = params.pop("database")
        connection = turso_serverless.connect(url, **params)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_cursor(self, name=None):
        if name is not None:
            raise NotSupportedError("Turso does not support named cursors.")
        return self.connection.cursor(factory=TursoCursorWrapper)

    def get_database_version(self):
        with self.cursor() as cursor:
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
        return tuple(int(part) for part in version.split("."))
