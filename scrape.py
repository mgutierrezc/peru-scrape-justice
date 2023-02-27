import argparse
import datetime
import functools
import os
import shutil
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
import urllib3

from captcha_solver import azcaptcha_solver_post
from constants import list_all_comb
from utils import (
    download_wait,
    is_element_present,
    setup_browser_driver,
    kill_os_process,
    cleat_temp_folder,
    logger,
)

load_dotenv()


LINK = "https://cej.pj.gob.pe/cej/forms/busquedaform.html"
PLACEHOLDER_TEXT = "--SELECCIONAR"
DONE_FLAG = "NO MORE FILES"

default_temp_download_folder = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "temp_downloads"
)

faulty_downloads_dir = os.path.join(
    os.path.realpath(os.path.dirname(__file__)), "faulty_downloads"
)
final_data_folder = os.path.join(os.path.realpath(os.path.dirname(__file__)), "data")

if not os.path.exists(faulty_downloads_dir):
    p = Path(faulty_downloads_dir)
    p.mkdir(parents=True)

NUMBER_OF_WORKERS = int(os.getenv("NUMBER_OF_WORKERS", 10))
drivers = []
threads = []
global_executor = None


def mark_combo_file_num_done(combo, file_num, parent_dir):
    done_dir = os.path.join(parent_dir, "done")
    if not os.path.exists(done_dir):
        Path(done_dir).mkdir(parents=True)
    done_file_path = os.path.join(done_dir, get_done_filename(combo, file_num))
    Path(done_file_path).touch()


def mark_combo_done(combo, parent_dir):
    done_dir = os.path.join(parent_dir, "done")
    if not os.path.exists(done_dir):
        Path(done_dir).mkdir(parents=True)
    done_file_path = os.path.join(done_dir, get_done_filename(combo))
    Path(done_file_path).touch()


def is_combo_file_num_done(combo, file_num, parent_dir):
    done_dir = os.path.join(parent_dir, "done")
    done_file_path = os.path.join(done_dir, get_done_filename(combo, file_num))
    return os.path.exists(done_file_path)


def validate_locations_choice(value):
    choices = list(c[0] for c in list_all_comb)
    if value in choices or value == "":
        return value
    raise argparse.ArgumentTypeError(
        f"{value} is not a valid choice. Available choices: {choices}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape course case data from https://cej.pj.gob.pe/cej/forms/busquedaform.html"
    )
    current_year = datetime.datetime.now().year
    parser.add_argument(
        "-y",
        "--years",
        dest="years",
        action="store",
        type=int,
        nargs="*",
        choices=list(range(2019, current_year + 1)),
        default=None,
        help="years to scrape, default to 2019",
        required=True,
    )
    parser.add_argument(
        "-l" "--locations",
        dest="locations",
        type=str,
        nargs="+",
        default=None,
        help="locations to scrape, default to all",
    )
    args = parser.parse_args()
    if args.locations:
        parsed_location_list = [s.strip() for s in ",".join(args.locations).split(",")]
        parsed_location_list = [
            validate_locations_choice(s) for s in parsed_location_list if s
        ]
        return parsed_location_list, args.years
    return None, args.years


def get_latest_locations():
    cleat_temp_folder(default_temp_download_folder)
    logger.info("Terminating previous firefox processes..")
    kill_os_process("firefox")
    try:
        driver = setup_browser_driver(default_temp_download_folder)
        driver.get(LINK)
        loc_dropdown = Select(driver.find_element(By.ID, "distritoJudicial"))
        locations = set(option.text for option in loc_dropdown.options)
        locations.remove(PLACEHOLDER_TEXT)
        driver.quit()
        return locations

    except (
        NoSuchElementException,
        TimeoutException,
        StaleElementReferenceException,
        WebDriverException,
    ) as e:
        logger.error(e)
        exit(2)


def get_done_filename(combo, file_num=None):
    arr = combo
    if file_num is not None:
        arr = combo + ["file_num", str(file_num)]
    return "_".join(arr)


def get_year_done_filename(year):
    return os.path.join(final_data_folder, str(year), "done")


def get_all_valid_years():
    driver = setup_browser_driver(default_temp_download_folder)
    driver.get(LINK)
    element = WebDriverWait(driver, 10).until(
        EC.text_to_be_present_in_element((By.ID, "anio"), PLACEHOLDER_TEXT)
    )
    loc_dropdown = Select(driver.find_element(By.ID, "anio"))
    years = set(option.text for option in loc_dropdown.options)
    years.remove(PLACEHOLDER_TEXT)
    driver.quit()
    return sorted([int(y) for y in years], reverse=True)


def get_parent_raw_html_dir(year):
    return os.path.join(final_data_folder, str(year), "raw_html")


def is_year_done(year):
    return os.path.exists(get_year_done_filename(year))


def is_combo_done(combo, parent_dir):
    done_file_path = os.path.join(parent_dir, "done", get_done_filename(combo))
    return os.path.exists(done_file_path)


def mark_year_done(year):
    Path(get_year_done_filename(year)).touch()


# stop event
stop_event = threading.Event()


class Scrapper:
    def __init__(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def scrape_data(
        self, driver, temp_downloads_dir, location_name
    ):  # to scrape the insides of the site
        button_list = []  # To scrape the button type links of the documents
        try:
            button_list = driver.find_elements(
                By.XPATH, '//div[@class="celdCentro"]/form/button'
            )
        except (
            NoSuchElementException,
            TimeoutException,
            StaleElementReferenceException,
            WebDriverException,
        ):
            logger.error(
                "Error occurred in getting button links, restarting scraping from the current file number"
            )
            driver.quit()
            raise RuntimeError("Error Occurred")
        table_html = []
        case_names_list = []
        if len(button_list) == 0:
            no_files_flag = True
        else:
            no_files_flag = False
        logger.info(f"button list: {len(button_list)}")

        for index in range(len(button_list)):
            logger.info(
                "--" + str(index) + "--"
            )  # This will tell you which doc is being processed

            # wait 10 seconds before looking for element
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[@class="celdCentro"]/form/button')
                    )
                )
            except (
                NoSuchElementException,
                TimeoutException,
                StaleElementReferenceException,
                WebDriverException,
            ):
                driver.quit()
                logger.warning(
                    "Error occurred in getting button links, restarting scraping from the current file number"
                )
                raise RuntimeError("Error Occurred")

            button_list = []
            button_list = driver.find_elements(
                By.XPATH, '//div[@class="celdCentro"]/form/button'
            )
            try:
                button_list[index].click()
            except (ElementNotInteractableException, ElementClickInterceptedException):
                driver.execute_script(
                    f'document.querySelectorAll("div.celdCentro form button")[{index}].click()'
                )
            logger.info(str(index) + " button clicked")

            ############################################################################################################
            # Important part of the code, while scraping htmls, it might not load after clicking just once, this way of doing it if it does not load solves the issue
            link_1 = None
            attempts = 0

            while not link_1:
                try:
                    link_1 = driver.find_element(By.XPATH, '//div[@class="partes"]')
                except NoSuchElementException:
                    button_list = []
                    button_list = driver.find_elements(
                        By.XPATH, '//div[@class="celdCentro"]/form/button'
                    )
                    if index < len(button_list):
                        button_list[index].click()

                    attempts += 1
                    if attempts >= 5:
                        return None, None, None
            #############################################################################################################

            html = driver.page_source
            table_html.append(html)

            # driver.execute_script("var scrollingElement = (document.scrollingElement ||
            # document.body);scrollingElement.scrollTop = scrollingElement.scrollHeight;")

            if is_element_present(
                "xpath", '//div[@class="celdaGrid celdaGridXe"]', driver
            ):
                tags = driver.find_elements(
                    By.XPATH, '//div[@class="celdaGrid celdaGridXe"]'
                )
            else:
                logger.warning(
                    "Error occured, restarting scraping from the current file number"
                )
                raise RuntimeError("Error Occured")

            for tag_index in range(len(tags)):
                case_names_list.append(tags[tag_index].text)

            # for downloading the documents

            elements_doc = []
            logger.info({"case_names_list:": case_names_list})
            try:
                if is_element_present(
                    "xpath", '//div[@class="panel panel-default divResolPar"]', driver
                ):
                    elements_doc = driver.find_elements(By.CLASS_NAME, "aDescarg")
                    expediente_n = driver.find_element(
                        By.CLASS_NAME, "celdaGrid.celdaGridXe"
                    ).text
                    expediente_year = expediente_n.split("-")[1]

                    existing_faulty_files = os.listdir(faulty_downloads_dir)
                    expediente_downloads_file = str(expediente_n) + ".txt"

                    if expediente_downloads_file in existing_faulty_files:
                        continue

                    for i in range(len(elements_doc)):
                        subfolder = str(expediente_n) + "_" + str(i + 1)

                        attributeValue_link = elements_doc[i].get_attribute("href")

                        target_download_dir = os.path.join(
                            final_data_folder,
                            expediente_year,
                            "downloaded_files",
                            location_name,
                            subfolder,
                        )

                        if not os.path.exists(target_download_dir):
                            p = Path(target_download_dir)
                            p.mkdir(parents=True)

                        # elements_doc[i].click()
                        WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(elements_doc[i])
                        ).click()
                        # driver.get(attributeValue_link)

                        link_path = target_download_dir + "/link.txt"
                        with open(link_path, "w+") as f:
                            f.write(str(attributeValue_link))

                        f.close()

                        timeout_time = (
                            10  # wait at max 10 seconds for a file to download
                        )
                        download_wait(temp_downloads_dir, timeout_time, driver, False)

                        file_names = os.listdir(temp_downloads_dir)
                        if len(file_names) > 0:
                            if not file_names[0].endswith(".part"):
                                temp_file_path = os.path.join(
                                    temp_downloads_dir, file_names[0]
                                )
                                shutil.move(temp_file_path, target_download_dir)

                        else:
                            logger.info("file not downloaded, will retry")
                            success = self.retry_download(
                                elements_doc[i],
                                4,
                                target_download_dir,
                                temp_downloads_dir,
                                driver,
                            )

                            if not success:
                                faulty_downloads_path = (
                                    f"{faulty_downloads_dir}/{expediente_n}.txt"
                                )
                                Path(faulty_downloads_path).touch()

            except (
                TimeoutException,
                StaleElementReferenceException,
                WebDriverException,
            ) as e:
                logger.warning(
                    f"Error occurred in getting links of download files, restarting scraping from the current file "
                    f"number:\n: {e}"
                )
                raise RuntimeError("Error Occurred")

            finally:
                element_back = "https://cej.pj.gob.pe/cej/forms/resumenform.html"
                driver.get(element_back)
        return table_html, case_names_list, no_files_flag

    # This function saves the extracted data in CSV format
    def html_saver(self, case_names_list, path, table_html):
        parent_dir = str(path) + "/"
        for index in range(len(table_html)):
            logger.info("--" + str(index) + "--")

            file = str(case_names_list[index]) + ".txt"

            with open(os.path.join(parent_dir, file), "w") as fp:
                fp.write(table_html[index])

    # For entering the site and scraping everything inside
    # This is the master function
    # Please do not tamper with the sleep timers anywhere in this code
    def scraper(self, file_num, list_comb, driver, year, temp_downloads_dir):
        driver.get(LINK)
        # driver.maximize_window()
        # wait 10 seconds before looking for element
        try:
            element = WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element(
                    (By.ID, "distritoJudicial"), PLACEHOLDER_TEXT
                )
            )

            # selecting LIMA
            select = Select(driver.find_element(By.ID, "distritoJudicial"))
            select.select_by_visible_text(str(list_comb[0]))

            # wait 10 seconds before looking for element
            element = WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, "anio"), PLACEHOLDER_TEXT)
            )

            # selecting YEAR
            select = Select(driver.find_element(By.ID, "anio"))
            select.select_by_visible_text(str(year))

            # For JUZGADO DE PAZ LETRADO

            # wait 10 seconds before looking for element

            element = WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element(
                    (By.ID, "organoJurisdiccional"), PLACEHOLDER_TEXT
                )
            )

            # Selecting instance of the case as JUZGADO DE PAZ LETRADO
            select = Select(driver.find_element(By.ID, "organoJurisdiccional"))
            select.select_by_visible_text(str(list_comb[1]))

            # Civil inside JUZGADO DE PAZ LETRADO

            # wait 10 seconds before looking for element
            element = WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element(
                    (By.ID, "especialidad"), PLACEHOLDER_TEXT
                )
            )

            select = Select(driver.find_element(By.ID, "especialidad"))
            select.select_by_visible_text(
                str(list_comb[2])
            )  # Set to civil, can be changed to any other type depending on the requirements of the user

            # input case file num
            inputElement = driver.find_element(By.ID, "numeroExpediente")
            inputElement.send_keys(file_num)

            # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.HOME)
            driver.execute_script(
                "var scrollingElement = (document.scrollingElement || document.body);scrollingElement.scrollTop = scrollingElement.scrollHeight;"
            )

            no_more_element_is_displayed = False
            sleep_time = 3
            index = 0
            while not is_element_present(
                "xpath", '//div[@class="celdCentro"]/form/button', driver
            ):
                if index != 0:
                    if is_element_present("id", "mensajeNoExisteExpedientes", driver):
                        no_more_element_is_displayed = driver.find_element(
                            By.ID, "mensajeNoExisteExpedientes"
                        ).is_displayed()
                    if no_more_element_is_displayed:
                        break
                    else:
                        if is_element_present("id", "btnReload", driver):
                            logger.warning(f"Captcha solved incorrectly, retrying...")
                            driver.find_element(By.ID, "btnReload").click()
                        time.sleep(3)
                if is_element_present("id", "btnReload", driver):
                    captcha_text = azcaptcha_solver_post(driver)
                    captcha = driver.find_element(By.ID, "codigoCaptcha")
                    captcha.clear()

                    captcha.send_keys(captcha_text)
                    driver.find_element(
                        By.XPATH, '//*[@id="consultarExpedientes"]'
                    ).click()
                while True:
                    try:
                        loader_is_displayed = driver.find_element(
                            By.ID, "cargando"
                        ).is_displayed()
                        if not loader_is_displayed:
                            break
                    except Exception as e:
                        break

                time.sleep(sleep_time)

                index += 1

            logger.info("Captcha solved correctly")

            if not no_more_element_is_displayed:
                parent_dir = get_parent_raw_html_dir(year)
                directory = "_".join(list_comb + ["file_num", str(file_num)])
                path = os.path.join(parent_dir, directory)
                if not os.path.exists(path):
                    Path(path).mkdir(parents=True)
                try:
                    logger.info(f"processing file_num: {file_num} for {list_comb}")
                    table_html, case_names_list, no_files = self.scrape_data(
                        driver, temp_downloads_dir, list_comb[0]
                    )
                except RuntimeError:
                    return self.scraper(
                        file_num, list_comb, driver, year, temp_downloads_dir
                    )

                if table_html is None and case_names_list is None:
                    logger.warning(
                        f"Failed to click form button, restarting file_num {file_num}"
                    )
                    return self.scraper(
                        file_num, list_comb, driver, year, temp_downloads_dir
                    )

                if no_files:
                    logger.info("NO MORE FILES, DELAYED ERROR")
                    flag = "NO MORE FILES, DELAYED ERROR"
                    return flag
                else:
                    self.html_saver(case_names_list, path, table_html)

                mark_combo_file_num_done(list_comb, file_num, parent_dir)
                combo_flag = "Combo Done"
                return combo_flag
            else:
                logger.info(f"NO MORE FILES for {list_comb}")
                return DONE_FLAG
        except Exception as e:

            if isinstance(e, KeyboardInterrupt) or isinstance(
                e, urllib3.exceptions.MaxRetryError
            ):
                stop_event.set()
            elif isinstance(e, PermissionError):
                logger.warning(
                    f"restarting scraping from the current file number due to PermissionError"
                )
                return self.scraper(
                    file_num, list_comb, driver, year, temp_downloads_dir
                )
            else:
                logger.error(f"Scrapper func error: {e}")

    def retry_download(
        self, link_el, max_tries, target_download_dir, temp_downloads_dir, driver
    ):
        tries = 1
        timeout_time = 10  # wait at max 10 seconds for a file to download
        success = False

        while tries < max_tries and not success:
            link_el.click()
            download_wait(temp_downloads_dir, timeout_time, driver, False)
            file_names = os.listdir(temp_downloads_dir)

            if len(file_names) > 0:
                temp_file_path = os.path.join(temp_downloads_dir, file_names[0])
                shutil.move(temp_file_path, target_download_dir)
                logger.info("downloaded on try : " + str(tries))
                success = True

            else:
                logger.info(
                    "file not downloaded on try "
                    + str(tries)
                    + " ,"
                    + str(max_tries - tries)
                    + " left"
                )
                tries = tries + 1

        return success

    def scrape_for_each_comb(self, list_comb, year, parent_raw_html_directory):

        if not stop_event.is_set():
            logger.info(f"Start processing {year} {list_comb}")

        file_number = (
            1  # reset case number to start from 1 for each location-court-type combo
        )
        flag = ""
        empty_num = 0
        temp_downloads_dir = os.path.join(
            default_temp_download_folder, "_".join(list_comb)
        )
        if not os.path.exists(temp_downloads_dir):
            p = Path(temp_downloads_dir)
            p.mkdir(parents=True)

        web_driver = setup_browser_driver(temp_downloads_dir)
        drivers.append(web_driver)

        while flag != DONE_FLAG and empty_num < 5 and not stop_event.is_set():
            if is_combo_file_num_done(
                list_comb, file_number, parent_raw_html_directory
            ):
                logger.info(f"Already done. Skipping {list_comb} {file_number}")
                file_number = file_number + 1
                continue

            flag = self.scraper(
                file_number, list_comb, web_driver, year, temp_downloads_dir
            )
            logger.info(f"{list_comb} file no {file_number}'s flag: {flag}")
            if flag == "NO MORE FILES, DELAYED ERROR":
                empty_num = empty_num + 1
                logger.info(
                    "File was empty, if next "
                    + str(5 - empty_num)
                    + " files are empty, next combination will start"
                )
            file_number = file_number + 1
        web_driver.quit()

        if not os.listdir(temp_downloads_dir):  # delete temp folder
            os.rmdir(temp_downloads_dir)

        mark_combo_done(list_comb, parent_raw_html_directory)
        return f"Done processing {year} {list_comb}"


def keyboard_cancle(signal, frame):
    logger.warning("Received Ctrl-C. Stopping threads...")
    stop_event.set()
    kill_os_process("firefox")
    sys.exit(0)


signal.signal(signal.SIGINT, keyboard_cancle)


def worker(semaphore, location_list, scrape_year, parent_raw_html_dir):
    try:
        while not stop_event.is_set():
            semaphore.acquire()
            logger.info(f"acquired semaphore")
            try:
                scrapper = Scrapper()
                scrapper.scrape_for_each_comb(
                    location_list, scrape_year, parent_raw_html_dir
                )
            except urllib3.exceptions.ProtocolError as e:
                stop_event.set()
                kill_os_process("firefox")
                sys.exit(0)

            semaphore.release()
            logger.info(f"released semaphore")
    except KeyboardInterrupt as e:
        logger.error(f"worker error: {e}")
        stop_event.set()
        kill_os_process("firefox")
        sys.exit(0)

if __name__ == "__main__":
    locations, years = parse_args()
    valid_locations = get_latest_locations()
    logger.info(
        f"All valid locations according to the current location dropdown menu: {valid_locations}"
    )

    if not years:
        years = get_all_valid_years()

    for scrape_year in years:
        if is_year_done(scrape_year):
            logger.info(f"Skipping {scrape_year} as it is already done")
            continue

        try:
            locations_to_use = list_all_comb
            if locations and len(locations) > 0:
                locations_to_use = [
                    x for x in list_all_comb if x[0] in locations
                ]  # only use parsed locations

            futures = []

            max_workers = (
                NUMBER_OF_WORKERS
                if NUMBER_OF_WORKERS <= len(locations_to_use)
                else NUMBER_OF_WORKERS - (NUMBER_OF_WORKERS - len(locations_to_use))
            )
            # Create a semaphore with a maximum of concurrent threads
            semaphore = threading.Semaphore(max_workers)
            for location_list in locations_to_use:
                parent_raw_html_dir = get_parent_raw_html_dir(scrape_year)

                if is_combo_done(location_list, parent_raw_html_dir):
                    logger.info(
                        f"Skipping {scrape_year} {location_list} as it is already done"
                    )
                    continue

                if locations and location_list[0] not in locations:
                    continue

                if location_list[0] not in valid_locations:
                    logger.warning(
                        f"Skipping {location_list} as {location_list[0]} is not found in the current location dropdown menu"
                    )
                    continue

                t = threading.Thread(
                    target=worker,
                    args=(semaphore, location_list, scrape_year, parent_raw_html_dir),
                )
                threads.append(t)

        except (Exception, KeyboardInterrupt) as e:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(e).__name__, e.args)
            logger.error(f"pool error: {message}")
            stop_event.set()
            kill_os_process("firefox")
            sys.exit(0)

    # Start all threads at the same time
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    if not locations and not stop_event.is_set():
        mark_year_done(scrape_year)
