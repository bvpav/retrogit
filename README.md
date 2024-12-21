# RetroGit

RetroGit is a git wrapper that helps you create commits with dates spread across a past time period. It's perfect for when you've been procrastinating on a project and want your commit history to look more... consistent.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

You can use RetroGit in two ways:

### 1. Direct Command

Instead of using `git commit`, use `retrogit commit`:

```bash
retrogit commit -m "Your commit message"
```

All normal git commit arguments are supported.

### 2. Pre-commit Hook

Alternatively, you can install RetroGit as a pre-commit hook, which will automatically set the commit dates when you use regular `git commit`:

```bash
retrogit install
```

This will install the pre-commit hook in your repository. After installation, you can just use `git commit` normally, and RetroGit will automatically set the commit dates.

## Configuration

Create a configuration file in your system's appropriate location:

- Linux/Unix: `$XDG_CONFIG_HOME/retrogit/config.toml` or `~/.config/retrogit/config.toml`
- Windows: `%APPDATA%\RetroGit\config.toml`
- Other systems: `~/.retrogit.toml`

Configuration format:

```toml
[timing]
# Average days between commits
interval_days = 3
# Random variation in days (will be added/subtracted from interval)
randomness_days = 1
# How far back to start when there are no commits (default: 30)
initial_backdate_days = 30
```

The configuration directory will be automatically created when you first run the tool.

## How it works

RetroGit takes your commits and automatically sets their dates to a time in the past, maintaining a natural-looking commit frequency based on your configuration. It starts from your last commit date (or repository creation date) and spaces out new commits according to your specified interval and randomness settings. For the first commit in a repository, it starts from `initial_backdate_days` ago.
