"""
SENTINAL v2 — Phase 5 integration smoke tests.
Verifies that all Phase 5 artifacts exist and are correctly wired.
Runs without Docker, GPU, or a running server.
"""

import asyncio
import os
import sys
import unittest

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestPhase5Integration(unittest.TestCase):

    def test_db_module_loads_and_init_db_is_async(self):
        """engine.storage.db loads cleanly and init_db is a coroutine function."""
        from engine.storage import db
        self.assertTrue(
            asyncio.iscoroutinefunction(db.init_db),
            "init_db must be an async function"
        )
        # Verify all required public functions exist
        for fn in ['init_db', 'insert_event', 'get_events', 'get_identities',
                   'upsert_identity', 'get_stats']:
            self.assertTrue(hasattr(db, fn), f"db module missing: {fn}")

    def test_docker_files_exist(self):
        """All Phase 5 Docker/config files are present at expected paths."""
        root = os.path.join(os.path.dirname(__file__), '..')
        files = {
            'Dockerfile': os.path.join(root, 'Dockerfile'),
            'dashboard/Dockerfile': os.path.join(root, 'dashboard', 'Dockerfile'),
            'docker-compose.yml': os.path.join(root, 'docker-compose.yml'),
            'dashboard/nginx.conf': os.path.join(root, 'dashboard', 'nginx.conf'),
        }
        for name, path in files.items():
            self.assertTrue(os.path.isfile(path), f"Missing file: {name}")

    def test_zones_page_in_app(self):
        """App.jsx contains the /zones route and Zones import."""
        root = os.path.join(os.path.dirname(__file__), '..')
        app_path = os.path.join(root, 'dashboard', 'src', 'App.jsx')
        self.assertTrue(os.path.isfile(app_path), "App.jsx not found")
        content = open(app_path, encoding='utf-8').read()
        self.assertIn('/zones', content, "App.jsx missing /zones route")
        self.assertIn('Zones', content, "App.jsx missing Zones import")

    def test_asyncpg_in_requirements(self):
        """requirements.txt contains asyncpg and psycopg2-binary entries."""
        root = os.path.join(os.path.dirname(__file__), '..')
        req_path = os.path.join(root, 'requirements.txt')
        self.assertTrue(os.path.isfile(req_path), "requirements.txt not found")
        content = open(req_path, encoding='utf-8').read()
        self.assertIn('asyncpg', content, "requirements.txt missing asyncpg")
        self.assertIn('psycopg2-binary', content, "requirements.txt missing psycopg2-binary")


if __name__ == '__main__':
    unittest.main()
