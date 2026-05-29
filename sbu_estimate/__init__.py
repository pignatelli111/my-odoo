import warnings

# Odoo.sh marks builds yellow on any WARNING in install.log (including py.warnings / docutils).
warnings.filterwarnings(
    'ignore',
    message='Cannot parse header or footer.*',
    category=UserWarning,
)
warnings.filterwarnings(
    'ignore',
    message='.*Block quote ends without a blank line.*',
)

from . import models
from . import wizards
from .hooks import post_init_hook
