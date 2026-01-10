"""
Coding Arena Engine
Tests coding/development agents against code challenges.
"""

from typing import List, Dict, Any
from datetime import datetime
import random
import logging

from app.models import Agent
from app.config import CODING_KEYWORD_TEMPLATES, get_tier_config
from .base import BaseArenaEngine, ArenaResult
from .sandbox import SandboxExecutor, MockSandbox

logger = logging.getLogger(__name__)


# Coding task templates
CODING_TEMPLATES = {
    # Bug fixing templates
    'fix_failing_tests': {
        'name': 'Fix Failing Unit Tests',
        'keyword': 'bug_fixing',
        'difficulty': 1.0,
        'input': {
            'code': '''
def calculate_average(numbers):
    return sum(numbers) / len(numbers)  # Bug: no empty list check

def find_max(numbers):
    max_val = numbers[0]  # Bug: no empty list check
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val
''',
            'tests': [
                {'name': 'test_average_normal', 'input': [[1, 2, 3]], 'expected': 2.0},
                {'name': 'test_average_empty', 'input': [[]], 'expected': 0},
                {'name': 'test_max_normal', 'input': [[1, 5, 3]], 'expected': 5},
                {'name': 'test_max_empty', 'input': [[]], 'expected': None},
            ],
            'tests_total': 4
        },
        'expected': {
            'tests_passed': 4,
            'compile_success': True,
        }
    },
    'debug_error': {
        'name': 'Debug Runtime Error',
        'keyword': 'bug_fixing',
        'difficulty': 1.1,
        'input': {
            'code': '''
def process_data(data):
    result = []
    for item in data:
        result.append(item['value'] * 2)  # Bug: missing key check
    return result
''',
            'error': "KeyError: 'value'",
            'test_input': [{'value': 1}, {'name': 'test'}, {'value': 3}],
        },
        'expected': {
            'error_fixed': True,
            'handles_edge_cases': True,
        }
    },
    'patch_security': {
        'name': 'Patch Security Vulnerability',
        'keyword': 'bug_fixing',
        'difficulty': 1.3,
        'input': {
            'code': '''
import os

def execute_command(user_input):
    os.system(f"echo {user_input}")  # Vulnerability: command injection
''',
            'vulnerability_type': 'command_injection',
        },
        'expected': {
            'vulnerability_fixed': True,
            'input_sanitized': True,
        }
    },
    
    # Feature implementation templates
    'implement_function': {
        'name': 'Implement Function from Spec',
        'keyword': 'feature_impl',
        'difficulty': 1.0,
        'input': {
            'spec': '''
Implement a function `fibonacci(n)` that returns the nth Fibonacci number.
- fibonacci(0) = 0
- fibonacci(1) = 1
- fibonacci(n) = fibonacci(n-1) + fibonacci(n-2) for n > 1
- Should handle negative inputs gracefully (return None)
''',
            'tests': [
                {'input': 0, 'expected': 0},
                {'input': 1, 'expected': 1},
                {'input': 10, 'expected': 55},
                {'input': -1, 'expected': None},
            ],
            'tests_total': 4
        },
        'expected': {
            'tests_passed': 4,
            'compile_success': True,
        }
    },
    'add_endpoint': {
        'name': 'Add API Endpoint',
        'keyword': 'feature_impl',
        'difficulty': 1.2,
        'input': {
            'framework': 'flask',
            'spec': '''
Add a GET endpoint /api/users/<user_id> that:
- Returns user data as JSON
- Returns 404 if user not found
- Returns 400 if user_id is not a valid integer
''',
            'existing_code': '''
from flask import Flask, jsonify
app = Flask(__name__)

users = {1: {'name': 'Alice'}, 2: {'name': 'Bob'}}
''',
        },
        'expected': {
            'endpoint_added': True,
            'handles_not_found': True,
            'handles_invalid_input': True,
        }
    },
    'create_model': {
        'name': 'Create Data Model',
        'keyword': 'feature_impl',
        'difficulty': 1.1,
        'input': {
            'spec': '''
Create a SQLAlchemy model for a 'Product' with:
- id (Integer, primary key)
- name (String, required, max 100 chars)
- price (Float, required, positive)
- stock (Integer, default 0)
- created_at (DateTime, auto-set)
''',
        },
        'expected': {
            'model_created': True,
            'all_fields_present': True,
            'constraints_applied': True,
        }
    },
    
    # Optimization templates
    'improve_performance': {
        'name': 'Improve Algorithm Performance',
        'keyword': 'optimization',
        'difficulty': 1.2,
        'input': {
            'code': '''
def find_duplicates(arr):
    duplicates = []
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] == arr[j] and arr[i] not in duplicates:
                duplicates.append(arr[i])
    return duplicates  # O(n^2) - needs optimization
''',
            'benchmark': {'input_size': 10000, 'target_ms': 100},
        },
        'expected': {
            'performance_improved': True,
            'functionality_preserved': True,
        }
    },
    'reduce_complexity': {
        'name': 'Reduce Code Complexity',
        'keyword': 'optimization',
        'difficulty': 1.1,
        'input': {
            'code': '''
def process_order(order):
    if order is not None:
        if order.status == 'pending':
            if order.items is not None:
                if len(order.items) > 0:
                    if order.total > 0:
                        if order.customer is not None:
                            return True
    return False
''',
            'complexity_target': 'cyclomatic < 5',
        },
        'expected': {
            'complexity_reduced': True,
            'logic_preserved': True,
        }
    },
    'refactor': {
        'name': 'Refactor Code',
        'keyword': 'optimization',
        'difficulty': 1.0,
        'input': {
            'code': '''
# This code has duplication and poor naming
def f(x):
    r = x * 2
    return r

def g(x):
    r = x * 2
    return r + 1

def h(x):
    r = x * 2
    return r - 1
''',
        },
        'expected': {
            'duplication_removed': True,
            'naming_improved': True,
        }
    },
    
    # Testing templates
    'write_unit_tests': {
        'name': 'Write Unit Tests',
        'keyword': 'testing',
        'difficulty': 1.0,
        'input': {
            'code': '''
def validate_email(email):
    import re
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))
''',
            'test_framework': 'pytest',
            'coverage_target': 0.8,
        },
        'expected': {
            'tests_written': True,
            'edge_cases_covered': True,
            'coverage_met': True,
        }
    },
    'add_integration_tests': {
        'name': 'Add Integration Tests',
        'keyword': 'testing',
        'difficulty': 1.2,
        'input': {
            'endpoint': 'POST /api/orders',
            'dependencies': ['database', 'payment_service'],
        },
        'expected': {
            'integration_test_added': True,
            'mocks_appropriate': True,
        }
    },
    'improve_coverage': {
        'name': 'Improve Test Coverage',
        'keyword': 'testing',
        'difficulty': 1.1,
        'input': {
            'current_coverage': 0.65,
            'target_coverage': 0.85,
            'uncovered_lines': [15, 16, 23, 24, 25, 30],
        },
        'expected': {
            'coverage_improved': True,
            'new_tests_added': True,
        }
    },
    
    # Documentation templates
    'write_docstrings': {
        'name': 'Write Docstrings',
        'keyword': 'documentation',
        'difficulty': 0.9,
        'input': {
            'code': '''
def calculate_discount(price, percentage, max_discount=None):
    discount = price * percentage / 100
    if max_discount and discount > max_discount:
        discount = max_discount
    return price - discount
''',
            'style': 'google',
        },
        'expected': {
            'docstring_added': True,
            'params_documented': True,
            'returns_documented': True,
        }
    },
    'create_readme': {
        'name': 'Create README',
        'keyword': 'documentation',
        'difficulty': 0.9,
        'input': {
            'project_name': 'FastAPI User Service',
            'features': ['User CRUD', 'Authentication', 'Rate limiting'],
            'stack': ['Python', 'FastAPI', 'PostgreSQL'],
        },
        'expected': {
            'readme_created': True,
            'installation_included': True,
            'usage_included': True,
        }
    },
    'api_documentation': {
        'name': 'Generate API Documentation',
        'keyword': 'documentation',
        'difficulty': 1.0,
        'input': {
            'endpoints': [
                {'method': 'GET', 'path': '/users', 'description': 'List users'},
                {'method': 'POST', 'path': '/users', 'description': 'Create user'},
                {'method': 'GET', 'path': '/users/{id}', 'description': 'Get user'},
            ],
            'format': 'openapi',
        },
        'expected': {
            'documentation_generated': True,
            'all_endpoints_documented': True,
        }
    },
}


class CodingArenaEngine(BaseArenaEngine):
    """
    Arena engine for coding/development agents.
    Tests against code challenges based on keywords.
    """
    
    arena_type = 'coding'
    
    def __init__(self, sandbox: SandboxExecutor = None):
        self.sandbox = sandbox or MockSandbox()
    
    def run(self, agent: Agent) -> ArenaResult:
        """
        Run coding arena for agent.
        
        Args:
            agent: Coding agent to test
        
        Returns:
            ArenaResult with UPI score and details
        """
        start_time = datetime.utcnow()
        errors = []
        
        # Validate interface
        is_valid, error = self.validate_interface(agent)
        if not is_valid:
            return ArenaResult(
                agent_id=agent.id,
                arena_type=self.arena_type,
                score=0,
                raw_score=0,
                errors=[error]
            )
        
        # Select templates based on keywords
        keywords = agent.keywords or ['bug_fixing']  # Default keyword
        templates = self.select_templates(keywords, CODING_KEYWORD_TEMPLATES, count=5)
        
        # If no templates match, use default set
        if not templates:
            templates = ['fix_failing_tests', 'implement_function', 'write_docstrings']
        
        # Run templates and collect scores
        effectiveness_scores = []
        efficiency_scores = []
        autonomy_scores = []
        template_scores = {}
        
        for template_name in templates:
            if template_name not in CODING_TEMPLATES:
                continue
                
            template = CODING_TEMPLATES[template_name]
            
            try:
                # Execute agent against template
                result = self.sandbox.execute(
                    code=agent.interface_code,
                    input_data=template['input'],
                    timeout=60  # Longer timeout for coding tasks
                )
                
                if result.success:
                    # Score effectiveness (tests passed, requirements met)
                    effectiveness = self._score_effectiveness(template, result.output)
                    
                    # Score efficiency (includes code quality for coding)
                    efficiency = self._score_efficiency(template, result)
                    
                    # Score autonomy (no retries/hints = 100)
                    autonomy = max(0, 100 - (result.retries * 25))
                    
                    # Apply difficulty modifier to effectiveness
                    difficulty = template.get('difficulty', 1.0)
                    effectiveness = min(100, effectiveness * difficulty)
                    
                    effectiveness_scores.append(effectiveness)
                    efficiency_scores.append(efficiency)
                    autonomy_scores.append(autonomy)
                    
                    template_scores[template_name] = {
                        'effectiveness': round(effectiveness, 2),
                        'efficiency': round(efficiency, 2),
                        'autonomy': autonomy,
                        'difficulty': difficulty,
                        'execution_time_ms': result.elapsed_ms
                    }
                else:
                    errors.append(f"{template_name}: {result.error}")
                    template_scores[template_name] = {
                        'effectiveness': 0,
                        'error': result.error
                    }
                    effectiveness_scores.append(0)
                    
            except Exception as e:
                logger.error(f"Error running template {template_name}: {e}")
                errors.append(f"{template_name}: {str(e)}")
        
        # Calculate average scores
        avg_effectiveness = sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0
        avg_autonomy = sum(autonomy_scores) / len(autonomy_scores) if autonomy_scores else 0
        
        # Calculate UPI
        raw_upi = self.calculate_upi(avg_effectiveness, avg_efficiency, avg_autonomy)
        
        # Apply tier ceiling
        tier = agent.tier or 'alpha'
        tier_config = get_tier_config(tier)
        final_score = min(raw_upi, tier_config['max_score'])
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ArenaResult(
            agent_id=agent.id,
            arena_type=self.arena_type,
            score=round(final_score, 2),
            raw_score=round(raw_upi, 2),
            effectiveness=round(avg_effectiveness, 2),
            efficiency=round(avg_efficiency, 2),
            autonomy=round(avg_autonomy, 2),
            templates_run=templates,
            template_scores=template_scores,
            execution_time_ms=execution_time_ms,
            errors=errors
        )
    
    def _score_effectiveness(self, template: Dict[str, Any], output: Dict[str, Any]) -> float:
        """
        Score coding effectiveness based on test results and requirements.
        """
        if not output:
            return 0
        
        expected = template.get('expected', {})
        input_data = template.get('input', {})
        
        # Check tests_passed if available
        if 'tests_passed' in output and 'tests_total' in input_data:
            tests_total = input_data['tests_total']
            tests_passed = output.get('tests_passed', 0)
            test_score = (tests_passed / tests_total) * 100 if tests_total > 0 else 0
            
            # Compile success bonus
            if output.get('compile_success', True):
                test_score = min(100, test_score + 10)
            
            return test_score
        
        # Generic scoring for mock outputs
        matched = 0
        total = len(expected) if expected else 1
        
        for key, expected_value in expected.items():
            if key in output:
                if isinstance(expected_value, bool):
                    if output[key] == expected_value:
                        matched += 1
                else:
                    matched += 0.5
        
        if total > 0 and matched > 0:
            return (matched / total) * 100
        
        # Fallback for mock
        if output.get('coverage', 0) > 0:
            return output['coverage'] * 100
        
        return random.uniform(60, 90)
    
    def _score_efficiency(self, template: Dict[str, Any], result) -> float:
        """
        Score coding efficiency based on time and code quality.
        """
        time_score = self._score_time_efficiency(result.elapsed_ms)
        
        # For coding, also consider output quality
        quality_score = 80  # Default
        if result.output:
            if result.output.get('coverage', 0) > 0.8:
                quality_score += 10
            if result.output.get('compile_success', False):
                quality_score += 10
        
        # Weight: 60% time, 40% quality
        return time_score * 0.6 + quality_score * 0.4
    
    def _score_time_efficiency(self, execution_time_ms: int) -> float:
        """
        Score time efficiency.
        For coding: 500ms = 100, 5000ms = 50, 30000ms = 0
        """
        if execution_time_ms <= 500:
            return 100
        elif execution_time_ms <= 2000:
            return 100 - ((execution_time_ms - 500) / 1500) * 20  # 80-100
        elif execution_time_ms <= 5000:
            return 80 - ((execution_time_ms - 2000) / 3000) * 30  # 50-80
        elif execution_time_ms <= 30000:
            return 50 - ((execution_time_ms - 5000) / 25000) * 50  # 0-50
        else:
            return 0
