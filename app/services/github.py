"""
GitHub Integration Service
Fetches and validates agent code from public GitHub repositories.
"""

import logging
import requests

logger = logging.getLogger(__name__)

GITHUB_RAW_BASE = "https://raw.githubusercontent.com"


class GitHubService:
    """Service for GitHub repository interactions."""
    
    @staticmethod
    def fetch_file(repo_url: str, branch: str = 'main', file_path: str = 'agent.py') -> dict:
        """
        Fetch a file from a public GitHub repository.
        
        Args:
            repo_url: Full GitHub URL (e.g., https://github.com/username/repo)
            branch: Branch name (default: main)
            file_path: Path to file in repo (default: agent.py)
        
        Returns:
            dict with 'success', 'content', 'commit_sha', 'error'
        """
        try:
            # Parse repo URL
            repo_url = repo_url.rstrip('/')
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
            
            parts = repo_url.replace('https://github.com/', '').split('/')
            if len(parts) < 2:
                return {'success': False, 'error': 'Invalid GitHub URL format'}
            
            owner = parts[0]
            repo = parts[1]
            
            # Fetch raw file content
            raw_url = f"{GITHUB_RAW_BASE}/{owner}/{repo}/{branch}/{file_path}"
            response = requests.get(raw_url, timeout=10)
            
            if response.status_code == 404:
                return {'success': False, 'error': f'File not found: {file_path} on branch {branch}'}
            elif response.status_code != 200:
                return {'success': False, 'error': f'GitHub returned status {response.status_code}'}
            
            content = response.text
            
            # Get latest commit SHA (optional)
            commit_sha = None
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}/commits?path={file_path}&sha={branch}&per_page=1"
                commit_response = requests.get(api_url, timeout=5)
                if commit_response.status_code == 200:
                    commits = commit_response.json()
                    if commits:
                        commit_sha = commits[0]['sha'][:7]
            except:
                pass
            
            return {
                'success': True,
                'content': content,
                'commit_sha': commit_sha,
                'raw_url': raw_url
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'GitHub request timed out'}
        except Exception as e:
            logger.error(f"GitHub fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def validate_code(content: str, arena_type: str = 'trading') -> dict:
        """
        Validate that the fetched code contains required function signature.
        """
        errors = []
        warnings = []
        
        if not content or not content.strip():
            errors.append('File is empty')
            return {'valid': False, 'errors': errors, 'warnings': warnings}
        
        # Check for required function
        if 'def decide(' not in content:
            errors.append('Missing required function: def decide(...)')
        
        if 'return' not in content:
            errors.append('Function must have a return statement')
        
        # Warnings (non-blocking)
        if 'import os' in content or 'import subprocess' in content:
            warnings.append('Code contains potentially unsafe imports')
        
        if len(content) > 50000:
            warnings.append('Code file is very large (>50KB)')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'line_count': len(content.split('\n'))
          }
