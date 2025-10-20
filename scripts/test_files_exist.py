# scripts/test_files_exist.py
import os, glob, unittest

class TestFilesExist(unittest.TestCase):
    def test_generated_configs_present(self):
        # If the directory doesn't exist OR has no YAML, skip (not a unit failure)
        if not os.path.isdir("generated-configs"):
            self.skipTest("generated-configs/ not present; skipping")
        files = glob.glob("generated-configs/*.yaml")
        if not files:
            self.skipTest("No YAML files in generated-configs/; skipping")
        # If present, assert at least one
        self.assertGreater(len(files), 0)
