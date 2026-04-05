import os
import logging
import asyncio
from git import Repo
from datetime import datetime, timezone, timedelta

# Basic logging and git setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


os.environ["GIT_SSH_COMMAND"] = f'ssh -i /app/ed25519 -o StrictHostKeyChecking=no'

# Values from app registration
GIT_REPO_URL = os.getenv("GIT_REPO_URL")
GIT_REPO_PATH = os.getenv("GIT_REPO_PATH")

# Global variables
UPDATED_FILES = []
EMPTY_FOLDERS = []


def fetch_repo() -> Repo:
    logging.info("Setting up Git repository...")

    # Init git repository
    if os.path.exists(GIT_REPO_PATH):
        GIT_REPO = Repo(GIT_REPO_PATH)

        logging.info("Pulling latest changes...")
        GIT_REPO.remotes.origin.pull()
    else:
        logging.info("Cloning repository...")

        # Clone the repository using the custom SSH key
        GIT_REPO = Repo.clone_from(GIT_REPO_URL, GIT_REPO_PATH)

    return GIT_REPO


async def main():
    logging.info("Starting the synchronization process...")

    GIT_REPO = fetch_repo()

    for (root, dirs, files) in os.walk('data/', topdown=True):

        if not dirs and not files:
            print(f"Creating {root}/.gitkeep")
            open(f"{root}/.gitkeep", 'w').close()

        if ".gitkeep" in files and len(files) > 1:
            print(f"Removing {root}/.gitkeep")
            os.remove(f"{root}/.gitkeep")

    untracked_files = len(GIT_REPO.untracked_files)
    changed_files = len(GIT_REPO.index.diff(None))

    if untracked_files > 0 or changed_files > 0:
        logging.info(f"Detected {untracked_files} new files")
        logging.info(f"Detected {changed_files} changed files")
        logging.info("Pushing to Git...")
        GIT_REPO.git.add(A=True)
        GIT_REPO.index.commit("Automated commit: Sync GoodNotes with Git")
        GIT_REPO.remote().push()
    else:
        logging.info("No changes detected")

if __name__ == "__main__":
    asyncio.run(main())
