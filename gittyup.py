#!/usr/bin/env python3

import json
import os
import time
import tomllib
from pathlib import Path
import git
from git.exc import GitCommandError


def read_repo_url_from_toml(config_file: str) -> str:
    """Reads the repository URL from a TOML configuration file."""
    # TODO: properly serialise the config
    file = open(config_file, "rb")
    config_data = tomllib.load(file)
    url = config_data.get("repository", {}).get("url")
    if url:
        return url
    else:
        raise ValueError("Repository URL not found in the TOML file.")


def wait_for_updates(url, clone_dir="repo", check_interval=60):
    """
    Continuously tries pulling new changes from the remote repository and returns if there are new
    changes (i.e. if a pull results in a current HEAD being changed).

    This function should be called in a loop: every time it returns it means there are new changes
    so we should do something.

    Parameters:

    - repo_url: The URL of the remote Git repository.
    - clone_dir: The directory where the repository should be cloned or pulled.
    - check_interval: Time in seconds between pull checks.
    """
    while True:
        if clone_or_pull_repo(url, clone_dir):
            profile = Path(clone_dir) / "profile.json"
            if profile.exists():
                payload = json.loads(profile.read_text(encoding="utf-8"))
                # TODO: Publish local tedge command
                _ = payload

            return

        # Wait for the specified interval before checking again
        print(f"Waiting for {check_interval} seconds before the next pull check...")
        time.sleep(check_interval)


def clone_or_pull_repo(repo_url, clone_dir="repo") -> bool:
    """
    Pulls the new information from the remote repository to the local repository, if there is any.
    If local repository does not exist, it is cloned.

    Parameters:

    - repo_url: The URL of the remote Git repository.
    - clone_dir: The directory where the repository should be cloned or pulled.
    - check_interval: Time in seconds between pull checks.

    Returns:
    - bool: True if local HEAD got updated, False otherwise
    """
    if os.path.exists(clone_dir):
        # If the repository exists, try to pull the latest changes
        print(f"Pulling the latest changes in '{clone_dir}'...")

        repo = git.Repo(clone_dir)
        origin = repo.remotes.origin
        prev_commit = repo.head.commit

        try:
            fetch_info = origin.pull()[0]

        except GitCommandError as e:
            print(f"Error during git pull: {e}")

        if fetch_info.commit.hexsha != prev_commit.hexsha:
            print("Repository updated with new changes.")
            return True

        print("No new changes found. Repository is already up to date.")
        return False
    else:
        # If the repository doesn't exist, clone it
        print(f"Cloning the repository '{repo_url}' into '{clone_dir}'...")

        try:
            git.Repo.clone_from(repo_url, clone_dir)
        except GitCommandError as e:
            print(f"Error during git clone: {e}")

        print(f"Repository cloned into '{clone_dir}'.")

        return True


if __name__ == "__main__":
    repo_url = read_repo_url_from_toml("config.toml")
    # clone_or_pull_repo(repo_url)
    wait_for_updates(repo_url)
