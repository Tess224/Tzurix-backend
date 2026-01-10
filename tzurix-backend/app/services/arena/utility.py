"""
Utility Arena Engine
Tests utility/productivity agents against task templates.
"""

from typing import List, Dict, Any
from datetime import datetime
import random
import logging

from app.models import Agent
from app.config import UTILITY_KEYWORD_TEMPLATES, get_tier_config
from .base import BaseArenaEngine, ArenaResult
from .sandbox import SandboxExecutor, MockSandbox

logger = logging.getLogger(__name__)


# Utility task templates
UTILITY_TEMPLATES = {
    # Scheduling templates
    'schedule_no_conflicts': {
        'name': 'Schedule Without Conflicts',
        'keyword': 'scheduling',
        'difficulty': 1.0,
        'input': {
            'existing_events': [
                {'title': 'Meeting A', 'start': '09:00', 'end': '10:00'},
                {'title': 'Meeting B', 'start': '14:00', 'end': '15:00'},
            ],
            'new_events': [
                {'title': 'New Meeting 1', 'duration': 60},
                {'title': 'New Meeting 2', 'duration': 30},
                {'title': 'New Meeting 3', 'duration': 45},
            ],
            'working_hours': {'start': '08:00', 'end': '18:00'}
        },
        'expected': {
            'all_scheduled': True,
            'no_conflicts': True,
        }
    },
    'reschedule_meeting': {
        'name': 'Reschedule Cancelled Meeting',
        'keyword': 'scheduling',
        'difficulty': 1.1,
        'input': {
            'cancelled_meeting': {'title': 'Team Sync', 'original_time': '10:00', 'duration': 30},
            'attendee_availability': [
                {'name': 'Alice', 'free_slots': ['11:00-12:00', '15:00-16:00']},
                {'name': 'Bob', 'free_slots': ['11:00-12:00', '14:00-15:00']},
            ],
        },
        'expected': {
            'rescheduled': True,
            'all_attendees_available': True,
        }
    },
    'find_free_slot': {
        'name': 'Find Free Time Slot',
        'keyword': 'scheduling',
        'difficulty': 0.9,
        'input': {
            'calendar': [
                {'start': '09:00', 'end': '10:00'},
                {'start': '11:00', 'end': '12:00'},
                {'start': '14:00', 'end': '16:00'},
            ],
            'required_duration': 45,
            'working_hours': {'start': '08:00', 'end': '18:00'}
        },
        'expected': {
            'slot_found': True,
            'meets_duration': True,
        }
    },
    
    # Email templates
    'summarize_email': {
        'name': 'Summarize Email Thread',
        'keyword': 'email',
        'difficulty': 1.0,
        'input': {
            'email_thread': [
                {'from': 'alice@example.com', 'subject': 'Project Update', 'body': 'Here are the latest numbers...'},
                {'from': 'bob@example.com', 'subject': 'RE: Project Update', 'body': 'I have concerns about...'},
                {'from': 'alice@example.com', 'subject': 'RE: Project Update', 'body': 'Good point, let me clarify...'},
            ],
            'max_summary_length': 100
        },
        'expected': {
            'summary_accurate': True,
            'key_points_extracted': True,
        }
    },
    'draft_reply': {
        'name': 'Draft Email Reply',
        'keyword': 'email',
        'difficulty': 1.1,
        'input': {
            'original_email': {
                'from': 'client@example.com',
                'subject': 'Question about pricing',
                'body': 'Hi, I was wondering about your pricing for the enterprise plan...'
            },
            'context': 'Our enterprise plan starts at $99/month',
            'tone': 'professional'
        },
        'expected': {
            'addresses_question': True,
            'tone_appropriate': True,
        }
    },
    'categorize_inbox': {
        'name': 'Categorize Inbox Messages',
        'keyword': 'email',
        'difficulty': 1.0,
        'input': {
            'emails': [
                {'subject': 'Weekly Newsletter', 'from': 'newsletter@news.com'},
                {'subject': 'URGENT: Server Down', 'from': 'alerts@company.com'},
                {'subject': 'Meeting Request', 'from': 'boss@company.com'},
                {'subject': 'You won a prize!', 'from': 'spam@prize.com'},
            ],
            'categories': ['urgent', 'newsletter', 'meeting', 'spam', 'other']
        },
        'expected': {
            'all_categorized': True,
            'accuracy_threshold': 0.8,
        }
    },
    
    # Task tracking templates
    'update_task_status': {
        'name': 'Update Task Status',
        'keyword': 'task_tracking',
        'difficulty': 0.9,
        'input': {
            'task': {'id': 1, 'title': 'Complete report', 'status': 'in_progress'},
            'update': {'status': 'completed', 'completion_notes': 'Report submitted to manager'},
        },
        'expected': {
            'task_updated': True,
            'status_valid': True,
        }
    },
    'prioritize_tasks': {
        'name': 'Prioritize Task List',
        'keyword': 'task_tracking',
        'difficulty': 1.2,
        'input': {
            'tasks': [
                {'title': 'Fix critical bug', 'due': 'today', 'impact': 'high'},
                {'title': 'Update documentation', 'due': 'next week', 'impact': 'low'},
                {'title': 'Review PR', 'due': 'tomorrow', 'impact': 'medium'},
                {'title': 'Team meeting prep', 'due': 'today', 'impact': 'medium'},
            ],
        },
        'expected': {
            'prioritized_correctly': True,
            'considers_due_date': True,
            'considers_impact': True,
        }
    },
    'generate_report': {
        'name': 'Generate Status Report',
        'keyword': 'task_tracking',
        'difficulty': 1.1,
        'input': {
            'completed_tasks': 5,
            'pending_tasks': 3,
            'blocked_tasks': 1,
            'period': 'weekly',
        },
        'expected': {
            'report_generated': True,
            'includes_metrics': True,
        }
    },
    
    # Reminder templates
    'set_reminder': {
        'name': 'Set Reminder',
        'keyword': 'reminders',
        'difficulty': 0.8,
        'input': {
            'reminder': 'Call mom',
            'time': 'tomorrow at 3pm',
        },
        'expected': {
            'reminder_set': True,
            'time_parsed': True,
        }
    },
    'trigger_reminder': {
        'name': 'Trigger Due Reminder',
        'keyword': 'reminders',
        'difficulty': 0.9,
        'input': {
            'current_time': '15:00',
            'reminders': [
                {'text': 'Team standup', 'time': '14:00', 'triggered': True},
                {'text': 'Call mom', 'time': '15:00', 'triggered': False},
                {'text': 'Dinner reservation', 'time': '18:00', 'triggered': False},
            ],
        },
        'expected': {
            'correct_reminder_triggered': True,
        }
    },
    'recurring_reminder': {
        'name': 'Set Recurring Reminder',
        'keyword': 'reminders',
        'difficulty': 1.0,
        'input': {
            'reminder': 'Weekly team meeting',
            'recurrence': 'every Monday at 10am',
        },
        'expected': {
            'recurrence_parsed': True,
            'schedule_created': True,
        }
    },
    
    # Goal management templates
    'track_progress': {
        'name': 'Track Goal Progress',
        'keyword': 'goal_management',
        'difficulty': 1.0,
        'input': {
            'goal': {'title': 'Learn Spanish', 'target': 100, 'current': 45, 'unit': 'lessons'},
            'new_progress': 5,
        },
        'expected': {
            'progress_updated': True,
            'percentage_calculated': True,
        }
    },
    'suggest_next_steps': {
        'name': 'Suggest Next Steps',
        'keyword': 'goal_management',
        'difficulty': 1.2,
        'input': {
            'goal': {'title': 'Launch product', 'progress': 0.6},
            'completed_milestones': ['Design', 'Development', 'Testing'],
            'remaining_milestones': ['Marketing', 'Launch'],
        },
        'expected': {
            'suggestions_relevant': True,
            'considers_progress': True,
        }
    },
    'milestone_update': {
        'name': 'Update Milestone Status',
        'keyword': 'goal_management',
        'difficulty': 1.0,
        'input': {
            'goal_id': 1,
            'milestone': {'title': 'Complete MVP', 'status': 'in_progress'},
            'new_status': 'completed',
        },
        'expected': {
            'milestone_updated': True,
            'goal_progress_recalculated': True,
        }
    },
}


class UtilityArenaEngine(BaseArenaEngine):
    """
    Arena engine for utility/productivity agents.
    Tests against task templates based on keywords.
    """
    
    arena_type = 'utility'
    
    def __init__(self, sandbox: SandboxExecutor = None):
        self.sandbox = sandbox or MockSandbox()
    
    def run(self, agent: Agent) -> ArenaResult:
        """
        Run utility arena for agent.
        
        Args:
            agent: Utility agent to test
        
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
        keywords = agent.keywords or ['task_tracking']  # Default keyword
        templates = self.select_templates(keywords, UTILITY_KEYWORD_TEMPLATES, count=5)
        
        # If no templates match, use default set
        if not templates:
            templates = ['update_task_status', 'set_reminder', 'track_progress']
        
        # Run templates and collect scores
        effectiveness_scores = []
        efficiency_scores = []
        autonomy_scores = []
        template_scores = {}
        
        for template_name in templates:
            if template_name not in UTILITY_TEMPLATES:
                continue
                
            template = UTILITY_TEMPLATES[template_name]
            
            try:
                # Execute agent against template
                result = self.sandbox.execute(
                    code=agent.interface_code,
                    input_data=template['input'],
                    timeout=30
                )
                
                if result.success:
                    # Score effectiveness (task completion)
                    effectiveness = self._score_effectiveness(template, result.output)
                    
                    # Score efficiency (time/resources)
                    efficiency = self._score_efficiency(result.elapsed_ms)
                    
                    # Score autonomy (no retries = 100, each retry reduces by 25)
                    autonomy = max(0, 100 - (result.retries * 25))
                    
                    effectiveness_scores.append(effectiveness)
                    efficiency_scores.append(efficiency)
                    autonomy_scores.append(autonomy)
                    
                    template_scores[template_name] = {
                        'effectiveness': effectiveness,
                        'efficiency': efficiency,
                        'autonomy': autonomy,
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
        Score task effectiveness (0-100).
        """
        if not output:
            return 0
        
        expected = template.get('expected', {})
        matched = 0
        total = len(expected)
        
        if total == 0:
            # Use generic scoring for mock outputs
            if output.get('task_success') or output.get('task_completed'):
                return random.uniform(70, 95)
            return random.uniform(40, 70)
        
        for key, expected_value in expected.items():
            if key in output:
                if isinstance(expected_value, bool):
                    if output[key] == expected_value:
                        matched += 1
                elif isinstance(expected_value, (int, float)):
                    # Threshold check
                    if output.get(key, 0) >= expected_value:
                        matched += 1
                else:
                    matched += 0.5  # Partial credit for having the field
        
        return (matched / total) * 100 if total > 0 else 0
    
    def _score_efficiency(self, execution_time_ms: int) -> float:
        """
        Score efficiency based on execution time.
        Faster = better, with diminishing returns.
        """
        # Target: 200ms = 100, 1000ms = 50, 5000ms = 0
        if execution_time_ms <= 200:
            return 100
        elif execution_time_ms <= 500:
            return 100 - ((execution_time_ms - 200) / 300) * 20  # 80-100
        elif execution_time_ms <= 1000:
            return 80 - ((execution_time_ms - 500) / 500) * 30  # 50-80
        elif execution_time_ms <= 5000:
            return 50 - ((execution_time_ms - 1000) / 4000) * 50  # 0-50
        else:
            return 0
