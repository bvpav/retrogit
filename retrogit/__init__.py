#!/usr/bin/env python3

import os
import sys
import toml
import random
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
from dateutil.parser import parse as parse_date
import git
import platform

def get_config_path():
    system = platform.system()
    
    if system == "Linux" or system == "Darwin":
        # First try XDG Base Directory specification
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config_home:
            return Path(xdg_config_home) / 'retrogit' / 'config.toml'
        
        # Fallback to ~/.config
        return Path.home() / '.config' / 'retrogit' / 'config.toml'
    
    elif system == "Windows":
        # Use %APPDATA% on Windows
        appdata = os.environ.get('APPDATA')
        if appdata:
            return Path(appdata) / 'RetroGit' / 'config.toml'
        return Path.home() / 'AppData' / 'Roaming' / 'RetroGit' / 'config.toml'
    
    # Fallback for other systems
    return Path.home() / '.retrogit.toml'

def load_config():
    config_path = get_config_path()
    if not config_path.exists():
        # Create directory structure if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        return {
            'timing': {
                'interval_days': 3,
                'randomness_days': 1,
                'initial_backdate_days': 30  # How far back to start when there are no commits
            }
        }
    
    with open(config_path, 'r') as f:
        return toml.load(f)

def get_last_commit_date():
    """Get the date of the last commit, or a reasonable starting date if no commits exist."""
    try:
        repo = git.Repo('.')
        try:
            last_commit = next(repo.iter_commits())
            return last_commit.committed_datetime
        except (StopIteration, ValueError):
            # No commits yet - start from initial_backdate_days ago
            config = load_config()
            backdate_days = config['timing'].get('initial_backdate_days', 30)
            return datetime.now() - timedelta(days=backdate_days)
    except git.exc.InvalidGitRepositoryError:
        print("Error: Not a git repository", file=sys.stderr)
        sys.exit(1)

def calculate_next_commit_date(last_date, config):
    interval = config['timing']['interval_days']
    randomness = config['timing']['randomness_days']
    
    # Add random variation to interval
    actual_interval = random.uniform(
        interval - randomness,
        interval + randomness
    )
    
    return last_date + timedelta(days=actual_interval)

def setup_git_dates():
    """Set up the git dates for the next commit."""
    config = load_config()
    last_date = get_last_commit_date()
    next_date = calculate_next_commit_date(last_date, config)
    date_str = next_date.strftime('%Y-%m-%d %H:%M:%S')
    
    # Set environment variables for git
    os.environ['GIT_AUTHOR_DATE'] = date_str
    os.environ['GIT_COMMITTER_DATE'] = date_str
    
    return date_str

def cmd_commit():
    """Handle the commit subcommand."""
    if len(sys.argv) < 3:
        print("Usage: retrogit commit [git commit arguments]")
        sys.exit(1)
    
    date_str = setup_git_dates()
    
    # Prepare the git commit command with our custom date
    git_args = ['git', 'commit'] + sys.argv[2:]
    env = os.environ.copy()
    
    # Execute git commit with the modified dates
    try:
        result = subprocess.run(git_args, env=env, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

def cmd_pre_commit():
    """Handle the pre-commit hook."""
    try:
        date_str = setup_git_dates()
        print(f"RetroGit: Setting commit date to {date_str}")
        sys.exit(0)
    except Exception as e:
        print(f"RetroGit pre-commit hook error: {str(e)}", file=sys.stderr)
        sys.exit(1)

def cmd_install_hook():
    """Install the pre-commit hook."""
    try:
        repo = git.Repo('.')
        hook_path = Path(repo.git_dir) / 'hooks' / 'pre-commit'
        
        # Create hooks directory if it doesn't exist
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the hook script
        with open(hook_path, 'w') as f:
            f.write(f'''#!/bin/sh
# RetroGit pre-commit hook
{sys.executable} {os.path.abspath(__file__)} pre-commit
''')
        
        # Make the hook executable
        hook_path.chmod(0o755)
        print(f"Pre-commit hook installed at {hook_path}")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to install pre-commit hook: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: retrogit <command> [arguments]")
        print("\nCommands:")
        print("  commit     - Commit with a backdated timestamp")
        print("  pre-commit - Run as a pre-commit hook")
        print("  install    - Install the pre-commit hook")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == 'commit':
        cmd_commit()
    elif command == 'pre-commit':
        cmd_pre_commit()
    elif command == 'install':
        cmd_install_hook()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main() 