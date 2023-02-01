#!/usr/bin/env python
# coding: utf-8

import argparse
import asyncio
import datetime
import logging
import coloredlogs
# FOR SAVING
import os
import shutil
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, \
    StaleElementReferenceException, WebDriverException, \
    ElementNotInteractableException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

from captcha_solver import azcaptcha_solver_post
from constants import list_all_comb

load_dotenv()
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
coloredlogs.install(logger=logger)

LINK = 'https://cej.pj.gob.pe/cej/forms/busquedaform.html'
PLACEHOLDER_TEXT = "--SELECCIONAR"
DONE_FLAG = "NO MORE FILES"
CHROME_PATH = os.getenv(r"CHROME_PATH")

default_download_path = fr"{os.path.realpath(os.path.dirname(__file__))}\temp_downloads"

faulty_downloads_dir = 'faulty_downloads'

if not os.path.exists(faulty_downloads_dir):
    p = Path(faulty_downloads_dir)
    p.mkdir(parents=True)

NUMBER_OF_WORKERS = int(os.getenv("NUMBER_OF_WORKERS", 10))


def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--test-type")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if not os.path.exists(default_download_path):
        d_path = Path(default_download_path)
        d_path.mkdir(parents=True)
    chrome_options.add_experimental_option('prefs', {'download.default_directory': default_download_path})

    return chrome_options


def setup_chrome_driver():
    driver = webdriver.Chrome(executable_path=CHROME_PATH, options=get_chrome_options())
    return driver


# This function cross checks if the element we want to extract exists or not
# not using this will result in errors
def is_element_present(by, value, driver):
    try:
        driver.find_element(by=by, value=value)
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        return False
    return True


def scrape_data(driver):  # to scrape the insides of the site

    button_list = []  # To scrape the button type links of the documents
    try:
        button_list = driver.find_elements_by_xpath('//div[@class="celdCentro"]/form/button')
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        logging.error("Error occurred in getting button links, restarting scraping from the current file number")
        driver.quit()
        raise RuntimeError("Error Occurred")

    table_html = []
    case_names_list = []

    if len(button_list) == 0:
        no_files_flag = True
    else:
        no_files_flag = False

    logging.info(f"button list: {len(button_list)}")

    for index in range(len(button_list)):

        logging.info("--" + str(index) + "--")  # This will tell you which doc is being processed

        # wait 10 seconds before looking for element
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[@class="celdCentro"]/form/button')))
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
            driver.quit()
            logging.error("Error occurred in getting button links, restarting scraping from the current file number")
            raise RuntimeError("Error Occurred")

        button_list = []
        button_list = driver.find_elements_by_xpath('//div[@class="celdCentro"]/form/button')
        try:
            button_list[index].click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script(f'document.querySelectorAll("div.celdCentro form button")[{index}].click()')
        logging.info(str(index) + " button clicked")

        ############################################################################################################
        # Important part of the code, while scraping htmls, it might not load after clicking just once, this way of doing it if it does not load solves the issue
        link_1 = None
        attempts = 0

        while not link_1:
            try:
                link_1 = driver.find_element_by_xpath('//div[@class="partes"]')
            except NoSuchElementException:
                button_list = []
                button_list = driver.find_elements_by_xpath('//div[@class="celdCentro"]/form/button')
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

        if is_element_present("xpath", '//div[@class="celdaGrid celdaGridXe"]', driver):
            tags = driver.find_elements_by_xpath('//div[@class="celdaGrid celdaGridXe"]')
        else:
            logging.info("Error occured, restarting scraping from the current file number")
            raise RuntimeError("Error Occured")

        for tag_index in range(len(tags)):
            case_names_list.append(tags[tag_index].text)

        # for downloading the documents

        elements_doc = []
        logging.info({"case_names_list:": case_names_list})
        try:
            if is_element_present("xpath", '//div[@class="panel panel-default divResolPar"]', driver):
                elements_doc = driver.find_elements_by_class_name("aDescarg")
                expediente_n = driver.find_element_by_class_name("celdaGrid.celdaGridXe").text
                expediente_year = expediente_n.split("-")[1]

                existing_faulty_files = os.listdir(faulty_downloads_dir)
                expediente_downloads_file = str(expediente_n) + ".txt"

                if expediente_downloads_file in existing_faulty_files:
                    continue

                for i in range(len(elements_doc)):

                    subfolder = str(expediente_n) + "_" + str(i + 1)

                    attributeValue_link = elements_doc[i].get_attribute("href")

                    target_download_dir = fr"{os.path.realpath(os.path.dirname(__file__))}\{os.path.join('data', expediente_year, 'downloaded_files', subfolder)}"

                    if not os.path.exists(target_download_dir):
                        p = Path(target_download_dir)
                        p.mkdir(parents=True)

                    # elements_doc[i].click()
                    driver.get(attributeValue_link)

                    link_path = target_download_dir + "/link.txt"

                    with open(link_path, "w+") as f:
                        f.write(str(attributeValue_link))

                    f.close()

                    temp_downloads_dir = default_download_path
                    timeout_time = 10  # wait at max 10 seconds for a file to download
                    download_wait(temp_downloads_dir, timeout_time, False)

                    file_names = os.listdir(temp_downloads_dir)
                    if len(file_names) > 0:
                        temp_file_path = os.path.join(temp_downloads_dir, file_names[0])
                        shutil.move(temp_file_path, target_download_dir)
                        logging.info("downloaded")

                    else:
                        logging.info("file not downloaded, will retry")
                        success = retry_download(attributeValue_link, 4, target_download_dir, driver)

                        if not success:
                            faulty_downloads_path = f'{faulty_downloads_dir}/{expediente_n}.txt'
                            Path(faulty_downloads_path).touch()

        except (TimeoutException, StaleElementReferenceException, WebDriverException) as e:
            logging.error(
                f"Error occurred in getting links of download files, restarting scraping from the current file "
                f"number:\n: {e}")
            raise RuntimeError("Error Occurred")

        finally:
            element_back = "https://cej.pj.gob.pe/cej/forms/resumenform.html"
            driver.get(element_back)

    return table_html, case_names_list, no_files_flag


# This function saves the extracted data in CSV format
def html_saver(case_names_list, path, table_html):
    parent_dir = str(path) + "/"
    for index in range(len(table_html)):
        logging.info("--" + str(index) + "--")

        file = str(case_names_list[index]) + ".txt"

        with open(os.path.join(parent_dir, file), 'w') as fp:
            fp.write(table_html[index])


# For entering the site and scraping everything inside
# This is the master function
# Please do not tamper with the sleep timers anywhere in this code
def scraper(file_num, list_comb, driver, year):
    driver.get(LINK)
    # driver.maximize_window()
    # wait 10 seconds before looking for element
    try:
        element = WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element((By.ID, 'distritoJudicial'), PLACEHOLDER_TEXT))

        # selecting LIMA
        select = Select(driver.find_element_by_id('distritoJudicial'))
        select.select_by_visible_text(str(list_comb[0]))

        # wait 10 seconds before looking for element
        element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'anio'), PLACEHOLDER_TEXT))

        # selecting YEAR
        select = Select(driver.find_element_by_id('anio'))
        select.select_by_visible_text(str(year))

        # For JUZGADO DE PAZ LETRADO

        # wait 10 seconds before looking for element

        element = WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element((By.ID, 'organoJurisdiccional'), PLACEHOLDER_TEXT))

        # Selecting instance of the case as JUZGADO DE PAZ LETRADO
        select = Select(driver.find_element_by_id('organoJurisdiccional'))
        select.select_by_visible_text(str(list_comb[1]))

        # Civil inside JUZGADO DE PAZ LETRADO

        # wait 10 seconds before looking for element
        element = WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element((By.ID, 'especialidad'), PLACEHOLDER_TEXT))

        select = Select(driver.find_element_by_id('especialidad'))
        select.select_by_visible_text(str(
            list_comb[2]))  # Set to civil, can be changed to any other type depending on the requirements of the user

        # input case file num
        inputElement = driver.find_element_by_id("numeroExpediente")
        inputElement.send_keys(file_num)

        # driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.HOME)
        driver.execute_script(
            "var scrollingElement = (document.scrollingElement || document.body);scrollingElement.scrollTop = scrollingElement.scrollHeight;")

        no_more_element_is_displayed = False
        sleep_time = 3
        index = 0

        while not is_element_present('xpath', '//div[@class="celdCentro"]/form/button', driver):
            if index != 0:
                if is_element_present('id', 'mensajeNoExisteExpedientes', driver):
                    no_more_element_is_displayed = driver.find_element_by_id(
                        "mensajeNoExisteExpedientes").is_displayed()
                if no_more_element_is_displayed:
                    break
                else:
                    logging.error(
                        f"Error, captcha solved incorrectly, retrying...")
                    driver.find_element_by_id('btnReload').click()
                    time.sleep(3)

            captcha_text = azcaptcha_solver_post(driver)
            captcha = driver.find_element_by_id('codigoCaptcha')
            captcha.clear()

            captcha.send_keys(captcha_text)
            driver.find_element_by_xpath('//*[@id="consultarExpedientes"]').click()
            while True:
                try:
                    loader_is_displayed = driver.find_element_by_id('cargando').is_displayed()
                    if not loader_is_displayed:
                        break
                except Exception as e:
                    break

            time.sleep(sleep_time)

            index += 1

        if not no_more_element_is_displayed:
            logging.info("Captcha solved correctly")

            parent_dir = get_parent_raw_html_dir(year)
            directory = "_".join(list_comb + ["file_num", str(file_num)])
            path = os.path.join(parent_dir, directory)
            if not os.path.exists(path):
                Path(path).mkdir(parents=True)
            try:
                logging.info(f'processing file_num: {file_num} for {list_comb}')
                table_html, case_names_list, no_files = scrape_data(driver)
            except RuntimeError:
                return scraper(file_num, list_comb, year)

            if table_html is None and case_names_list is None:
                logging.warning(f"Failed to click form button, restarting file_num {file_num}")
                return scraper(file_num, list_comb, year)

            if no_files:
                logging.info("NO MORE FILES, DELAYED ERROR")
                flag = "NO MORE FILES, DELAYED ERROR"
                return flag
            else:
                html_saver(case_names_list, path, table_html)

            mark_combo_file_num_done(list_comb, file_num, parent_dir)
            combo_flag = "Combo Done"
            return combo_flag
        else:
            logging.info(f"NO MORE FILES for {list_comb}")
            return DONE_FLAG
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException) as e:
        driver.quit()
        logging.error({"debug_scraper": e})
        logging.error("Error occurred while filling details from list_comb on the first page. Exiting...")
        exit(2)


def get_parent_raw_html_dir(year):
    return os.path.join("data", str(year), "raw_html")


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


def mark_year_done(year):
    Path(get_year_done_filename(year)).touch()


def get_year_done_filename(year):
    return os.path.join("data", str(year), "done")


def is_year_done(year):
    return os.path.exists(get_year_done_filename(year))


def is_combo_file_num_done(combo, file_num, parent_dir):
    done_dir = os.path.join(parent_dir, "done")
    done_file_path = os.path.join(done_dir, get_done_filename(combo, file_num))
    return os.path.exists(done_file_path)


def is_combo_done(combo, parent_dir):
    done_file_path = os.path.join(parent_dir, "done", get_done_filename(combo))
    return os.path.exists(done_file_path)


def get_done_filename(combo, file_num=None):
    arr = combo
    if file_num is not None:
        arr = combo + ["file_num", str(file_num)]
    return "_".join(arr)


def check_model_file():
    pretrained_model_filename = 'TPS-ResNet-BiLSTM-Attn.pth'
    if not os.path.exists(pretrained_model_filename) or \
            os.path.getsize(pretrained_model_filename) < 100000000:
        logging.error(
            'ERROR: Pre-trained data model for captcha missing or incomplete. Try executing `git lfs pull` if your initial clone did not fetch this file.')
        exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Scrape course case data from https://cej.pj.gob.pe/cej/forms/busquedaform.html')
    current_year = datetime.datetime.now().year
    parser.add_argument('-y', '--years', dest='years', action='store', type=int,
                        nargs='*', choices=list(range(2019, current_year + 1)), default=None,
                        help='years to scrape, default to 2019')
    parser.add_argument('-l' '--locations', dest='locations', action='store', type=str,
                        nargs='*', choices=list(c[0] for c in list_all_comb), default=None,
                        help='locations to scrape, default to all')
    args = parser.parse_args()
    return args.locations, args.years


def get_latest_locations():
    try:
        driver = setup_chrome_driver()
        driver.get(LINK)
        loc_dropdown = Select(driver.find_element_by_id('distritoJudicial'))
        locations = set(option.text for option in loc_dropdown.options)
        locations.remove(PLACEHOLDER_TEXT)
        driver.quit()
        return locations

    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException) as e:
        logging.error(e)
        exit(2)


def get_all_valid_years():
    driver = setup_chrome_driver()
    driver.get(LINK)
    element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'anio'), PLACEHOLDER_TEXT))
    loc_dropdown = Select(driver.find_element_by_id('anio'))
    years = set(option.text for option in loc_dropdown.options)
    years.remove(PLACEHOLDER_TEXT)
    driver.quit()
    return sorted([int(y) for y in years], reverse=True)


def retry_download(link, max_tries, target_download_dir, driver):
    attr_link = link
    tries = 1
    timeout_time = 10  # wait at max 10 seconds for a file to download
    success = False

    while tries < max_tries and not success:
        driver.get(attr_link)
        download_wait(default_download_path, timeout_time, False)
        file_names = os.listdir(default_download_path)

        if len(file_names) > 0:
            temp_file_path = os.path.join(default_download_path, file_names[0])
            shutil.move(temp_file_path, target_download_dir)
            logging.info("downloaded on try : " + str(tries))
            success = True

        else:
            logging.info("file not downloaded on try " + str(tries) + " ," + str(max_tries - tries) + " left")
            tries = tries + 1

    return success


def download_wait(directory, timeout, nfiles=False):
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
            if fname.endswith('.crdownload'):
                dl_wait = True

        seconds += 1
    return seconds


def split_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def scrape_for_each_comb(list_comb, year, parent_raw_html_directory):
    logging.info(f'Start processing {year} {list_comb}')
    file_number = 1  # reset case number to start from 1 for each location-court-type combo
    flag = ""
    empty_num = 0
    web_driver = setup_chrome_driver()

    while flag != DONE_FLAG and empty_num < 5:
        if is_combo_file_num_done(list_comb, file_number, parent_raw_html_directory):
            logging.info(f"Already done. Skipping {list_comb} {file_number}")
            file_number = file_number + 1
            continue

        flag = scraper(file_number, list_comb, web_driver, year)
        logging.info(f"{list_comb} file no {file_number}'s flag: {flag}")
        if flag == "NO MORE FILES, DELAYED ERROR":
            empty_num = empty_num + 1
            logging.info("File was empty, if next " + str(
                5 - empty_num) + " files are empty, next combination will start")
        file_number = file_number + 1
    web_driver.quit()
    mark_combo_done(list_comb, parent_raw_html_directory)
    return f'Done processing {year} {list_comb}'


if __name__ == '__main__':

    check_model_file()
    locations, years = parse_args()
    valid_locations = get_latest_locations()
    logging.info(f'All valid locations according to the current location dropdown menu: {valid_locations}')

    if not years:
        years = get_all_valid_years()

    for scrape_year in years:
        if is_year_done(scrape_year):
            logging.info(f'Skipping {scrape_year} as it is already done')
            continue

        try:
            locations_to_use = list_all_comb
            if locations and len(locations) > 0:
                locations_to_use = [x for x in list_all_comb if x[0] in locations]  # only use parsed locations

            futures = []


            def signal_handler(signal, frame):
                executor.shutdown(wait=False)
                sys.exit(0)


            signal.signal(signal.SIGINT, signal_handler)
            max_workers = NUMBER_OF_WORKERS if NUMBER_OF_WORKERS <= len(locations_to_use) else NUMBER_OF_WORKERS - (
                        NUMBER_OF_WORKERS - len(locations_to_use))
            logging.info(f"Max workers set to: {max_workers}")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                try:
                    for location_list in locations_to_use:
                        parent_raw_html_dir = get_parent_raw_html_dir(scrape_year)

                        if is_combo_done(location_list, parent_raw_html_dir):
                            logging.info(f'Skipping {scrape_year} {location_list} as it is already done')
                            continue

                        if locations and location_list[0] not in locations:
                            continue

                        if location_list[0] not in valid_locations:
                            logging.warning(
                                f'Skipping {location_list} as {location_list[0]} is not found in the current location dropdown menu')
                            continue

                        futures.append(
                            executor.submit(scrape_for_each_comb, location_list, scrape_year, parent_raw_html_dir))

                    for future in as_completed(futures):
                        logging.info(future.result())


                except Exception as e:
                    executor.shutdown(wait=False, cancel_futures=True)

        except Exception as e:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(e).__name__, e.args)
            logging.error(f"pool error: {message}")
            raise

        if not locations:
            mark_year_done(scrape_year)
