import os, unittest, yaml
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = "template-generator/templates"   # adjust if needed
SAMPLE_YAML   = "generated-configs/sample.yaml"  # adjust if needed
SAMPLE_TPL    = "device.j2"                      # adjust if needed

@unittest.skipUnless(
    os.path.exists(SAMPLE_YAML) and os.path.exists(os.path.join(TEMPLATES_DIR, SAMPLE_TPL)),
    "Sample YAML/template missing; skipping render smoke test"
)
class TestTemplateRender(unittest.TestCase):
    def test_render(self):
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
        tpl = env.get_template(SAMPLE_TPL)
        with open(SAMPLE_YAML) as f:
            data = yaml.safe_load(f) or {}
        rendered = tpl.render(**data)
        self.assertTrue(isinstance(rendered, str) and rendered.strip())
