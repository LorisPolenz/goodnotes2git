import os
import logging
import asyncio
from git import Repo
from msgraph import GraphServiceClient
from datetime import datetime, timezone, timedelta
from azure.identity.aio import ClientSecretCredential

# Basic logging and git setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


os.environ["GIT_SSH_COMMAND"] = f'ssh -i /app/ed25519 -o StrictHostKeyChecking=no'

# Values from app registration
DRIVE_ID = os.getenv("DRIVE_ID")
ROOT_DIR_ID = os.getenv("ROOT_DIR_ID")
TEANT_ID = os.getenv("TEANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GIT_REPO_URL = os.getenv("GIT_REPO_URL")
GIT_REPO_PATH = os.getenv("GIT_REPO_PATH")

# Global variables
UPDATED_FILES = []
EMPTY_FOLDERS = []

# Init Microsoft Graph client
scopes = ['https://graph.microsoft.com/.default']

credential = ClientSecretCredential(
    tenant_id=TEANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET)

graph_client = GraphServiceClient(credential, scopes)


async def create_file(path, item_id):
    content = await graph_client.drives.by_drive_id(DRIVE_ID).items.by_drive_item_id(item_id).content.get()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(content)


async def create_empty_folder(path):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, '.gitkeep'), 'w') as f:
        f.write('')  # Create .gitkeep


async def map_children(drive_id: str, parent_item, path=str):
    res = await graph_client.drives.by_drive_id(drive_id).items.by_drive_item_id(parent_item.id).children.get()

    if len(res.value) == 0:
        logging.info(f"Empty folder detected: {path}")
        EMPTY_FOLDERS.append(path)
        return

    for item in res.value:
        if item.file:
            if item.last_modified_date_time < (datetime.now(tz=timezone.utc) - timedelta(minutes=15)):
                logging.debug(
                    f"Skipping {item.name} as it was not modified in the last 15 minutes - Last modifed: {item.last_modified_date_time}")
                continue

            logging.info(f"{path}/{item.name} ({item.file.mime_type})")
            UPDATED_FILES.append({
                "path": f"{path}/{item.name}",
                "id": item.id
            })

        if item.folder:
            await map_children(drive_id, item, path=path + '/' + item.name)


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
    root_result = await graph_client.drives.by_drive_id(DRIVE_ID)\
        .items.by_drive_item_id(ROOT_DIR_ID).children.get()

    for item in root_result.value:
        # Exclude archive directories
        if item.name.startswith('ZZ'):
            continue

        if item.folder:
            await map_children(DRIVE_ID, item, path=f"./{GIT_REPO_PATH}/{item.name}")

    if len(UPDATED_FILES) == 0 and len(EMPTY_FOLDERS) == 0:
        logging.info("No changes detected in the last 15 minutes. Exiting...")
        return

    GIT_REPO = fetch_repo()

    for file in UPDATED_FILES:
        logging.info(f"Processing file: {file['path']}")
        await create_file(file['path'], file['id'])

    for folder in EMPTY_FOLDERS:
        logging.info(f"Processing empty folder: {folder}")
        await create_empty_folder(folder)

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
