from django.db import connections
from django.test.runner import DiscoverRunner


class SupabaseTestRunner(DiscoverRunner):
    """
    Drops the test database with FORCE. Supabase's connection pooler keeps its server connection to the
    test database open after Django disconnects, so a plain DROP DATABASE fails with "being accessed by
    other users".
    """

    def teardown_databases(self, old_config, **kwargs):
        for connection, old_name, destroy in old_config:
            if not destroy or self.keepdb:
                continue
            test_name = connection.settings_dict["NAME"]
            connection.close()
            connection.settings_dict["NAME"] = old_name
            with connection._nodb_cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS {connection.ops.quote_name(test_name)} WITH (FORCE)")
        for alias in connections:
            connections[alias].close()
