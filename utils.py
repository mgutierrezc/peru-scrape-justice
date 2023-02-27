import os
from pathlib import Path
from random import uniform
import shutil
import subprocess
import sys
import time
import coloredlogs
import logging
import psutil
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.firefox.options import Options as firefox_options
from selenium.webdriver.firefox.service import Service as FirefoxService

load_dotenv()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
coloredlogs.install(logger=logger)

BROWSER_DRIVER_PATH = os.getenv(r"BROWSER_DRIVER_PATH")
FIREFOX_EXECUTABLE_PATH = os.getenv(r"FIREFOX_EXECUTABLE_PATH")


def get_firefox_options(download_path, is_headless):
    options = firefox_options()
    if is_headless:
        options.add_argument("-headless")

    options.binary_location = FIREFOX_EXECUTABLE_PATH

    if not os.path.exists(download_path):
        d_path = Path(download_path)
        d_path.mkdir(parents=True)

    options.set_preference("browser.download.dir", download_path)
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")
    return options


def set_up_firefox_profile():
    profile = webdriver.FirefoxProfile()
    profile.set_preference("security.fileuri.strict_origin_policy", False)
    profile.update_preferences()
    return profile


def setup_browser_driver(download_path, is_headless=True, is_proxy=False):
    if not BROWSER_DRIVER_PATH or not FIREFOX_EXECUTABLE_PATH:
        logger.error(
            "The following env are requied: BROWSER_DRIVER_PATH, FIREFOX_EXECUTABLE_PATH"
        )
    service_object = FirefoxService(executable_path=BROWSER_DRIVER_PATH)
    service_object.start()

    driver = webdriver.Firefox(
        options=get_firefox_options(download_path, is_headless),
        firefox_profile=set_up_firefox_profile(),
    )

    return driver


def is_windows_process_running(process_name):
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False


def kill_os_process(process):

    try:
        if sys.platform.startswith("linux"):
            subprocess.run(["pkill", process])
        elif sys.platform.startswith("win32"):
            if is_windows_process_running(f"{process}.exe"):
                os.system(f"taskkill /F /IM {process}.exe")
        else:
            pass
    except Exception:
        pass


def signal_handler(signal, frame):
    logger.warning("signal handler called")
    kill_os_process("firefox")


def download_wait(directory, timeout, driver, nfiles=False):
    """
    Wait for downloads to finish with a specified timeout.
    Args
    ----
    directory : str
        The path to the folder where the files will be downloaded.
    timeout : int
        How many seconds to wait until timing out.
    nfiles : int, defaults to None
        If provided, also wait for the expected number of files.

    Taken from - https://stackoverflow.com/questions/34338897/python-selenium-find-out-when-a-download-has-completed#:~:text=There%20is%20no%20built%2Din,file%20exists%20to%20read%20it
    """
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < timeout:
        time.sleep(1)
        dl_wait = False
        files = os.listdir(directory)
        if nfiles:
            if len(files) != nfiles:
                dl_wait = True

        for fname in files:
            if fname.endswith(".part"):
                dl_wait = True

        seconds += 1

    tabs = driver.window_handles
    if len(tabs) > 1:
        driver.switch_to.window(tabs[1])
        driver.close()
        driver.switch_to.window(tabs[0])

    return seconds


# This function cross checks if the element we want to extract exists or not
# not using this will result in errors
def is_element_present(by, value, driver):
    try:
        driver.find_element(by=by, value=value)
    except (
        NoSuchElementException,
        TimeoutException,
        StaleElementReferenceException,
        WebDriverException,
    ):
        return False
    return True


def cleat_temp_folder(temp_folder_path):
    # delete all the files in the folder
    for filename in os.listdir(temp_folder_path):
        file_path = os.path.join(temp_folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

    # delete all the subfolders in the folder
    for subfolder_name in os.listdir(temp_folder_path):
        subfolder_path = os.path.join(temp_folder_path, subfolder_name)
        try:
            if os.path.isdir(subfolder_path):
                shutil.rmtree(subfolder_path)
        except Exception as e:
            print(f"Failed to delete {subfolder_path}. Reason: {e}")
