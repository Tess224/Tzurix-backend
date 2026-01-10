"""
Admin Module
ISOLATED - Can be completely removed/disabled for production.

This module contains:
- Admin endpoints (score updates, migrations)
- Development utilities
- Debug routes

To disable: Set ENABLE_ADMIN=false in environment
"""

from .admin_bp import admin_bp

__all__ = ['admin_bp']
