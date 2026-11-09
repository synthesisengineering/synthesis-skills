"""`python -m kb_connector`: load the published tree, then serve it until stopped."""

import sys

from .server import main

sys.exit(main())
