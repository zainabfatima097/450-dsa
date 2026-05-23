import sys
from unittest.mock import MagicMock

# Pillow (PIL) doesn't support Python 3.14 yet.
# Mock it so tests that import from `app` can still collect and run.
if sys.version_info >= (3, 14):
    for _mod in ('PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont'):
        sys.modules.setdefault(_mod, MagicMock())
    sys.modules.setdefault('card_generator', MagicMock())
