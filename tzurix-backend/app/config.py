"""
Tzurix Configuration
All constants, environment variables, and tier definitions.
"""

import os


# =============================================================================
# ENVIRONMENT
# =============================================================================

ENV = os.environ.get('ENV', 'development')
IS_PRODUCTION = ENV == 'production'
DEBUG = not IS_PRODUCTION

# Database
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///tzurix_dev.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# External API keys
HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY')
BIRDEYE_API_KEY = os.environ.get('BIRDEYE_API_KEY')

# Auth keys
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'tzurix-dev-admin')
CRON_SECRET = os.environ.get('CRON_SECRET', 'tzurix-cron-secret')

# Feature flags
ENABLE_ADMIN = os.environ.get('ENABLE_ADMIN', 'true').lower() == 'true'
ENABLE_SCHEDULER = os.environ.get('START_SCHEDULER', 'false').lower() == 'true' or os.environ.get('RAILWAY_ENVIRONMENT')


# =============================================================================
# SCORING CONSTANTS (V1)
# =============================================================================

STARTING_SCORE = 20
DAILY_POINT_CAP = 5  # ±5 points max daily change
MIN_SCORE = 1
MAX_SCORE = 100

# Legacy cap (kept for backward compatibility)
DAILY_SCORE_CAP = 0.35  # ±35% max daily change


# =============================================================================
# PRICING CONSTANTS
# =============================================================================

TOTAL_SUPPLY = 100_000_000  # 100M tokens per agent stock
LAMPORTS_PER_SCORE_POINT = 67  # 67 lamports per score point
SOL_PRICE_USD = 150  # Default SOL price for USD conversion

# Trading
TRADE_FEE_PERCENT = 0.01  # 1% fee


# =============================================================================
# TIER SYSTEM
# =============================================================================

TIERS = {
    'alpha': {
        'name': 'Alpha',
        'emoji': '🛡️',
        'difficulty': 'Standard',
        'max_score': 75,
        'description': 'Standard difficulty - recommended for new agents',
    },
    'beta': {
        'name': 'Beta',
        'emoji': '⚔️',
        'difficulty': 'Advanced',
        'max_score': 90,
        'description': 'Advanced difficulty - harder scenarios, higher ceiling',
    },
    'omega': {
        'name': 'Omega',
        'emoji': '👑',
        'difficulty': 'Elite',
        'max_score': 100,
        'description': 'Elite difficulty - extreme scenarios, maximum potential',
    },
}


def get_tier_config(tier_name: str) -> dict:
    """Get configuration for a tier."""
    return TIERS.get(tier_name.lower(), TIERS['alpha'])


def get_tier_max_score(tier_name: str) -> int:
    """Get maximum score for a tier."""
    return get_tier_config(tier_name)['max_score']


# =============================================================================
# ARENA TYPES
# =============================================================================

ARENA_TYPES = ['trading', 'utility', 'coding']
VALID_AGENT_TYPES = ['trading', 'social', 'defi', 'utility', 'coding']


# =============================================================================
# UTILITY ARENA - KEYWORD TEMPLATES
# =============================================================================

UTILITY_KEYWORD_TEMPLATES = {
    'scheduling': ['schedule_no_conflicts', 'reschedule_meeting', 'find_free_slot'],
    'email': ['summarize_email', 'draft_reply', 'categorize_inbox'],
    'task_tracking': ['update_task_status', 'prioritize_tasks', 'generate_report'],
    'reminders': ['set_reminder', 'trigger_reminder', 'recurring_reminder'],
    'goal_management': ['track_progress', 'suggest_next_steps', 'milestone_update'],
    'research': ['summarize_document', 'extract_key_points', 'compare_sources'],
    'writing': ['draft_content', 'edit_grammar', 'suggest_improvements'],
}


# =============================================================================
# CODING ARENA - KEYWORD TEMPLATES
# =============================================================================

CODING_KEYWORD_TEMPLATES = {
    'bug_fixing': ['fix_failing_tests', 'debug_error', 'patch_security'],
    'feature_impl': ['implement_function', 'add_endpoint', 'create_model'],
    'optimization': ['improve_performance', 'reduce_complexity', 'refactor'],
    'testing': ['write_unit_tests', 'add_integration_tests', 'improve_coverage'],
    'documentation': ['write_docstrings', 'create_readme', 'api_documentation'],
}


# =============================================================================
# UPI (Universal Performance Index) WEIGHTS
# =============================================================================

UPI_WEIGHTS = {
    'effectiveness': 0.50,
    'efficiency': 0.30,
    'autonomy': 0.20,
}


# =============================================================================
# VERSION INFO
# =============================================================================

VERSION = '1.2.0'
VERSION_NAME = 'V1 Arena Update'
FEATURES = ['tier_system', 'arena_scoring', 'interface_upload', 'utility_arena', 'coding_arena']
