import os
import zipfile
import dropbox
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import WriteMode, FileMetadata
from dotenv import load_dotenv
from utils import logger

load_dotenv()
DROPBOX_ACCESS_TOKEN = os.getenv(r"DROPBOX_ACCESS_TOKEN")


local_data_folder_path = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "data"
)
local_log_file_path = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "scrape.log"
)
dropbox_file_path = "/peru-scrapper/scrape.log"
dropbox_data_folder_path = "/peru-scrapper/data"
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN, timeout=900.0)

try:
    with open(local_log_file_path, "rb") as f:
        dbx.files_upload(f.read(), dropbox_file_path)

    logger.info("log file uploaded.")

except Exception as e:
    logger.error(f"Dropbox uploader error: {e}")

logger.info("zipping data folder. Please wait...")
zip_file_path = os.path.join(
    local_data_folder_path, os.path.basename(local_data_folder_path) + ".zip"
)
with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(local_data_folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            zipf.write(file_path, os.path.relpath(file_path, local_data_folder_path))
logger.info("zipping completed. Now uploading...")
with open(zip_file_path, "rb") as f:
    try:
        dbx.files_upload(f.read(), dropbox_data_folder_path, mode=WriteMode.overwrite)
        print("Zip file uploaded successfully")
    except AuthError as e:
        print("Error authenticating with Dropbox:", e)
    except ApiError as e:
        print("Error uploading zip file to Dropbox:", e)
