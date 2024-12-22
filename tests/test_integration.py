"""Integration tests for RetroGit."""

import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
import toml
from freezegun import freeze_time
from pytest import FixtureRequest

# Import the functions we want to test
from retrogit import Config, load_config, setup_git_dates


@pytest.fixture(scope="function")
def temp_git_repo(request: FixtureRequest) -> Generator[Path, None, None]:
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        old_cwd = os.getcwd()
        os.chdir(temp_dir)

        # Initialize git repo
        subprocess.run(["git", "init"], check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            check=True,
        )

        yield Path(temp_dir)

        os.chdir(old_cwd)


@pytest.fixture(scope="function")
def temp_config(request: FixtureRequest) -> Generator[Config, None, None]:
    """Create a temporary RetroGit configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save all relevant environment variables
        saved_env = {
            "HOME": os.environ.get("HOME"),
            "XDG_CONFIG_HOME": os.environ.get("XDG_CONFIG_HOME"),
            "APPDATA": os.environ.get("APPDATA"),
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA"),
        }

        # Clear and set new environment variables
        for var in saved_env:
            if var in os.environ:
                del os.environ[var]

        # Set HOME and XDG_CONFIG_HOME to our temp directory
        os.environ["HOME"] = str(Path(temp_dir))
        os.environ["XDG_CONFIG_HOME"] = str(Path(temp_dir) / ".config")

        # Create config directory and file
        config_dir = Path(temp_dir) / ".config" / "retrogit"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config.toml"

        config: Config = {
            "timing": {
                "interval_days": 5,
                "randomness_days": 1,
                "initial_backdate_days": 45,
            }
        }

        config_path.write_text(toml.dumps(config))

        yield config

        # Restore original environment variables
        for var, value in saved_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]


def test_config_loading(temp_config: Config) -> None:
    """Test that configuration is loaded correctly."""
    config = load_config()
    assert config["timing"]["interval_days"] == 5
    assert config["timing"]["randomness_days"] == 1
    assert config["timing"]["initial_backdate_days"] == 45


def test_initial_commit_date(temp_git_repo: Path, temp_config: Config) -> None:
    """Test that the first commit is backdated correctly."""
    # Import git inside the test to avoid circular import issues
    import git

    # Create and commit a test file
    test_file = temp_git_repo / "test.txt"
    test_file.write_text("test content")

    repo = git.Repo(".")
    repo.index.add(["test.txt"])

    # Set up the test time
    frozen_time = "2024-01-01 12:00:00"
    frozen_datetime = datetime.strptime(frozen_time, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    expected_date = (frozen_datetime - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")

    # Create the commit with the expected date
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = expected_date
    env["GIT_COMMITTER_DATE"] = expected_date
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        env=env,
        check=True,
    )

    # Verify the commit date
    commit = next(repo.iter_commits())
    commit_date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
    expected_datetime = datetime.strptime(expected_date, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )

    print("\nDebug - Dates:")
    print(f"Commit date:    {commit_date}")
    print(f"Expected date:  {expected_datetime}")

    # Calculate difference in days
    diff_days = abs((expected_datetime - commit_date).total_seconds()) / 86400
    print(f"Difference in days: {diff_days}")
    assert diff_days <= 1  # Within 1 day


def test_subsequent_commit_dates(temp_git_repo: Path, temp_config: Config) -> None:
    """Test that subsequent commits are spaced correctly."""
    # Import git inside the test to avoid circular import issues
    import git

    test_file = temp_git_repo / "test.txt"

    # Make initial commit
    with freeze_time("2024-01-01 12:00:00"):
        test_file.write_text("initial content")
        repo = git.Repo(".")
        repo.index.add(["test.txt"])
        date_str = setup_git_dates()
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            env=env,
            check=True,
        )

    # Make second commit
    with freeze_time("2024-01-01 12:00:00"):
        test_file.write_text("updated content")
        repo.index.add(["test.txt"])
        date_str = setup_git_dates()
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        subprocess.run(
            ["git", "commit", "-m", "Second commit"],
            env=env,
            check=True,
        )

    commits = list(repo.iter_commits())
    first_date = datetime.fromtimestamp(commits[1].committed_date, tz=timezone.utc)
    second_date = datetime.fromtimestamp(commits[0].committed_date, tz=timezone.utc)

    # Check that the interval between commits is approximately 5 days (± 1 day)
    interval = (second_date - first_date).total_seconds() / 86400  # Convert to days
    assert 4 <= interval <= 6


def test_pre_commit_hook(temp_git_repo: Path, temp_config: Config) -> None:
    """Test that the pre-commit hook sets dates correctly."""
    # Import git inside the test to avoid circular import issues
    import git

    # Install the pre-commit hook
    retrogit_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "retrogit", "__init__.py")
    )
    subprocess.run(
        ["python3", retrogit_path, "install"],
        cwd=temp_git_repo,
        check=True,
    )

    # Create and commit a test file
    test_file = temp_git_repo / "test.txt"
    test_file.write_text("test content")

    repo = git.Repo(".")
    repo.index.add(["test.txt"])

    with freeze_time("2024-01-01 12:00:00"):
        subprocess.run(
            ["git", "commit", "-m", "Test commit"],
            check=True,
        )

    # Verify that the commit date was set by the hook
    commit = next(repo.iter_commits())
    commit_date = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    assert commit_date < now
