import os, glob, unittest

class TestFilesExist(unittest.TestCase):
    def test_generated_configs_present(self):
        # If your lab doesn't generate these yet, skip gracefully.
        if not os.path.isdir("generated-configs"):
            self.skipTest("generated-configs/ not present")
        files = glob.glob("generated-configs/*.yaml")
        self.assertGreater(len(files), 0, "No YAML files in generated-configs/")
