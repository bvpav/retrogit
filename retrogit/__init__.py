"""RetroGit - A git wrapper for creating commits with dates spread across a past time period."""

import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn, TypedDict, cast

import git
import toml


class TimingConfig(TypedDict):
    """Configuration for commit timing."""

    interval_days: int
    randomness_days: int
    initial_backdate_days: int


class Config(TypedDict):
    """RetroGit configuration."""

    timing: TimingConfig


def get_config_path() -> Path:
    """Get the path to the configuration file based on the operating system."""
    system = platform.system()

    if system == "Linux" or system == "Darwin":
        # First try XDG Base Directory specification
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / "retrogit" / "config.toml"

        # Fallback to ~/.config
        return Path.home() / ".config" / "retrogit" / "config.toml"

    elif system == "Windows":
        # Use %APPDATA% on Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "RetroGit" / "config.toml"
        return Path.home() / "AppData" / "Roaming" / "RetroGit" / "config.toml"

    # Fallback for other systems
    return Path.home() / ".retrogit.toml"


def load_config() -> Config:
    """Load the configuration from file or return default configuration."""
    config_path = get_config_path()
    if not config_path.exists():
        # Create directory structure if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Default configuration
        return {
            "timing": {
                "interval_days": 3,
                "randomness_days": 1,
                # How far back to start when there are no commits
                "initial_backdate_days": 30,
            }
        }

    with open(config_path, "r") as f:
        return cast(Config, toml.load(f))


def get_last_commit_date(skip_last: bool = False) -> datetime:
    """Get the date of the last commit, or a reasonable starting date if no commits exist.
    
    Args:
        skip_last: If True, skip the most recent commit and use the second-to-last commit's date.
                  This is useful for post-commit hooks where the most recent commit is the one we want to amend.
    """
    try:
        repo = git.Repo(".")
        try:
            commits = list(repo.iter_commits(max_count=2))  # Get up to 2 commits
            if not commits:
                # No commits yet - start from initial_backdate_days ago
                config = load_config()
                backdate_days = config["timing"].get("initial_backdate_days", 30)
                return datetime.now() - timedelta(days=backdate_days)
            
            # If skip_last is True and we have at least 2 commits, use the second-to-last commit
            if skip_last and len(commits) > 1:
                return cast(datetime, commits[1].committed_datetime)
            # Otherwise use the most recent commit
            return cast(datetime, commits[0].committed_datetime)
        except (StopIteration, ValueError):
            # No commits yet - start from initial_backdate_days ago
            config = load_config()
            backdate_days = config["timing"].get("initial_backdate_days", 30)
            return datetime.now() - timedelta(days=backdate_days)
    except git.exc.InvalidGitRepositoryError:
        print("Error: Not a git repository", file=sys.stderr)
        sys.exit(1)


def calculate_next_commit_date(last_date: datetime, config: Config) -> datetime:
    """Calculate the next commit date based on the last date and configuration."""
    interval = config["timing"]["interval_days"]
    randomness = config["timing"]["randomness_days"]

    # Add random variation to interval
    actual_interval = random.uniform(interval - randomness, interval + randomness)

    return last_date + timedelta(days=actual_interval)


def setup_git_dates(skip_last: bool = False) -> str:
    """Set up the git dates for the next commit.
    
    Args:
        skip_last: If True, skip the most recent commit and use the second-to-last commit's date.
                  This is useful for post-commit hooks where the most recent commit is the one we want to amend.
    """
    config = load_config()
    last_date = get_last_commit_date(skip_last=skip_last)
    next_date = calculate_next_commit_date(last_date, config)
    date_str = next_date.strftime("%Y-%m-%d %H:%M:%S")

    # Set environment variables for git
    os.environ["GIT_AUTHOR_DATE"] = date_str
    os.environ["GIT_COMMITTER_DATE"] = date_str

    return date_str


def cmd_commit() -> NoReturn:
    """Handle the commit subcommand."""
    if len(sys.argv) < 3:
        print("Usage: retrogit commit [git commit arguments]")
        sys.exit(1)

    setup_git_dates(skip_last=False)  # Explicitly set skip_last=False for direct commits

    # Prepare the git commit command with our custom date
    git_args = ["git", "commit"] + sys.argv[2:]
    env = os.environ.copy()

    # Execute git commit with the modified dates
    try:
        result = subprocess.run(git_args, env=env, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


def cmd_post_commit() -> NoReturn:
    """Handle the post-commit hook."""
    if "GIT_AUTHOR_DATE" not in os.environ:
        print(
            "RetroGit: Must be run as a post-commit hook. Install the hook using `retrogit install`",
            file=sys.stderr,
        )
        sys.exit(1)

    # If we are ammending a commit already, avoid amending it again
    if os.environ.get("RETROGIT_COMMIT_AMENDED") == "1":
        sys.exit(0)

    try:
        date_str = setup_git_dates(skip_last=True)  # Use skip_last=True for post-commit hook

        print(f"RetroGit: Setting commit date to {date_str} and amending commit")
        env = os.environ.copy()
        env["RETROGIT_COMMIT_AMENDED"] = "1"  # Prevent infinite loops
        subprocess.run(
            ["git", "commit", "--amend", "--no-edit", "--date", date_str],
            env=env,
            check=True,
        )
        sys.exit(0)
    except Exception as e:
        print(f"RetroGit post-commit hook error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cmd_install_hook() -> NoReturn:
    """Install the post-commit hook."""
    try:
        repo = git.Repo(".")
        hook_path = Path(repo.git_dir) / "hooks" / "post-commit"

        # Create hooks directory if it doesn't exist
        hook_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the hook script
        with open(hook_path, "w") as f:
            f.write(
                f"""#!/bin/sh
# RetroGit post-commit hook
{sys.executable} {os.path.abspath(__file__)} post-commit
"""
            )

        # Make the hook executable
        hook_path.chmod(0o755)
        print(f"Post-commit hook installed at {hook_path}")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to install post-commit hook: {str(e)}", file=sys.stderr)
        sys.exit(1)


def main() -> NoReturn:
    """Run the RetroGit tool."""
    if len(sys.argv) < 2:
        print("Usage: retrogit <command> [arguments]")
        print("\nCommands:")
        print("  commit      - Commit with a backdated timestamp")
        print("  post-commit - Run as a post-commit hook")
        print("  install     - Install the post-commit hook")
        sys.exit(1)

    command = sys.argv[1]
    if command == "commit":
        cmd_commit()
    elif command == "post-commit":
        cmd_post_commit()
    elif command == "install":
        cmd_install_hook()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
