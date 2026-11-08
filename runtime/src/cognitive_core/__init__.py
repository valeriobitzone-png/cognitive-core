"""Universal Cognitive Core: local-first cognitive substrate.

All optional model and web dependencies are OFF by default.
"""
__version__ = "1.4.0rc3"

from .config import Settings
from .engine import CognitiveCore

__all__ = ["CognitiveCore", "Settings"]
