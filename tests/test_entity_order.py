"""Entity output must not depend on Python's per-process randomized set order."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class EntityOrderTests(unittest.TestCase):
    def test_case_variants_have_same_order_across_processes(self):
        code = "from newsrag.entity_rules import refine; import json; print(json.dumps(refine({'companies':['RPG group','RPG Group'],'people':[],'locations':[]}, [], 'RPG group and RPG Group')[0]['companies']))"
        for seed in ('1', '2', '3', '4', '5', '10'):
            result = subprocess.run([sys.executable, '-c', code],
                                    cwd=Path(__file__).resolve().parents[1],
                                    env=dict(os.environ, PYTHONHASHSEED=seed),
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), ['RPG Group', 'RPG group'])
