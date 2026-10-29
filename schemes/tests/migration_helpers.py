from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def applied_migration_apps():
    """Match historical models to every migration actually left in the test DB."""
    loader = MigrationExecutor(connection).loader
    applied = [node for node in loader.applied_migrations if node in loader.graph.nodes]
    return loader.project_state(applied).apps
