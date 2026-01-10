"""
Tzurix App Package
AI Agent Performance Exchange Backend
"""

from .config import VERSION, VERSION_NAME
from .models import db

__version__ = VERSION
__all__ = ['db', 'VERSION', 'VERSION_NAME']
