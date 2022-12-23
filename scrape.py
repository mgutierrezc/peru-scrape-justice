#!/usr/bin/env python
# coding: utf-8

import argparse
import datetime
import logging
# FOR SAVING
import os
import shutil
import time
from pathlib import Path

from dotenv import load_dotenv
# FOR CAPTCHA
# importing relevant libraries
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

LINK = 'https://cej.pj.gob.pe/cej/forms/busquedaform.html'
PLACEHOLDER_TEXT = "--SELECCIONAR"
DONE_FLAG = "NO MORE FILES"
CHROME_PATH = os.getenv(r"CHROME_PATH")

global driver


# This function cross checks if the element we want to extract exists or not
# not using this will result in errors
def is_element_present(by, value):
    try:
        driver.find_element(by=by, value=value)
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        return False
    return True


def get_captcha_text_via_utterance_text(driver):
    driver.find_element_by_xpath('//*[@id="btnReload"]').click()
    time.sleep(5)
    hidden_text_value = driver.find_element_by_id('1zirobotz0').get_attribute('value')
    return hidden_text_value


def scrape_data():  # to scrape the insides of the site

    button_list = []  # To scrape the button type links of the documents
    try:
        button_list = driver.find_elements_by_xpath('//div[@class="celdCentro"]/form/button')
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        logging.info("Error occurred in getting button links, restarting scraping from the current file number")
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
            logging.info("Error occurred in getting button links, restarting scraping from the current file number")
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

        if is_element_present("xpath", '//div[@class="celdaGrid celdaGridXe"]'):
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
            if is_element_present("xpath", '//div[@class="panel panel-default divResolPar"]'):
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

                    target_download_dir = rf"{Path(__file__).parent / os.path.join('data', expediente_year, 'downloaded_files', subfolder)}"

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
                        success = retry_download(attributeValue_link, 4, target_download_dir)

                        if not success:
                            faulty_downloads_path = f'{faulty_downloads_dir}/{expediente_n}.txt'
                            Path(faulty_downloads_path).touch()

        except (TimeoutException, StaleElementReferenceException, WebDriverException):
            driver.quit()
            logging.info(
                "Error occurred in getting links of download files, restarting scraping from the current file number")
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
def scraper(file_num, list_comb, year):
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
        while not is_element_present('xpath', '//div[@class="celdCentro"]/form/button'):
            if index != 0:
                if is_element_present('id', 'mensajeNoExisteExpedientes'):
                    no_more_element_is_displayed = driver.find_element_by_id(
                        "mensajeNoExisteExpedientes").is_displayed()
                if no_more_element_is_displayed:
                    break
                else:
                    logging.error(
                        f"Error, captcha solved incorrectly, retrying..., wait time: {sleep_time} seconds")
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
                logging.info(f'processing file_num: {file_num}')
                table_html, case_names_list, no_files = scrape_data()
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
        logging.info({"debug_scraper": e})
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


def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--test-type")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if not os.path.exists(default_download_path):
        p = Path(default_download_path)
        p.mkdir(parents=True)
    chrome_options.add_experimental_option('prefs', {'download.default_directory': default_download_path})

    return chrome_options


def get_latest_locations():
    try:
        driver_0 = webdriver.Chrome(executable_path=CHROME_PATH, options=get_chrome_options())

        # driver = webdriver.Chrome(executable_path=CHROME_PATH, options=get_chrome_options())
        driver_0.get(LINK)
        # element = WebDriverWait(driver, 10).until(
        #     EC.text_to_be_present_in_element((By.ID, 'distritoJudicial'), PLACEHOLDER_TEXT))
        # loc_dropdown =  WebDriverWait(driver, 10).until(
        #     EC.text_to_be_present_in_element((By.ID, 'distritoJudicial'), PLACEHOLDER_TEXT))
        loc_dropdown = Select(driver_0.find_element_by_id('distritoJudicial'))
        locations = set(option.text for option in loc_dropdown.options)
        locations.remove(PLACEHOLDER_TEXT)
        driver_0.quit()
        return locations

    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException) as e:
        logging.info(e)
        exit(2)


def get_all_valid_years():
    driver = webdriver.Chrome(executable_path=CHROME_PATH, options=get_chrome_options())
    driver.get(LINK)
    element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'anio'), PLACEHOLDER_TEXT))
    loc_dropdown = Select(driver.find_element_by_id('anio'))
    years = set(option.text for option in loc_dropdown.options)
    years.remove(PLACEHOLDER_TEXT)
    return sorted([int(y) for y in years], reverse=True)


def retry_download(link, max_tries, target_download_dir):
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


global default_download_path
default_download_path = os.getenv("DOWNLOAD_PATH")

global faulty_downloads_dir
faulty_downloads_dir = 'faulty_downloads'

if not os.path.exists(faulty_downloads_dir):
    p = Path(faulty_downloads_dir)
    p.mkdir(parents=True)

if __name__ == '__main__':

    check_model_file()
    locations, years = parse_args()
    valid_locations = get_latest_locations()
    logging.info(f'All valid locations according to the current location dropdown menu: {valid_locations}')

    if not years:
        years = get_all_valid_years()

    for year in years:
        if is_year_done(year):
            logging.info(f'Skipping {year} as it is already done')
            continue

        for list_comb in list_all_comb:
            parent_raw_html_dir = get_parent_raw_html_dir(year)
            if is_combo_done(list_comb, parent_raw_html_dir):
                logging.info(f'Skipping {year} {list_comb} as it is already done')
                continue

            if locations and list_comb[0] not in locations:
                continue

            if list_comb[0] not in valid_locations:
                logging.warning(
                    f'Skipping {list_comb} as {list_comb[0]} is not found in the current location dropdown menu')
                continue

            logging.info(f'Start processing {year} {list_comb}')
            file_num = 1  # reset case number to start from 1 for each location-court-type combo
            flag = ""
            empty_num = 0

            while flag != DONE_FLAG and empty_num < 5:
                if is_combo_file_num_done(list_comb, file_num, parent_raw_html_dir):
                    logging.info(f"Already done. Skipping {list_comb} {file_num}")
                    file_num = file_num + 1
                    continue
                try:
                    driver = webdriver.Chrome(executable_path=CHROME_PATH, options=get_chrome_options())
                except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
                    driver.quit()
                    logging.info("Error occurred in opening Chrome, restarting scraping from the current file number")

                flag = scraper(file_num, list_comb, year)
                if flag == "NO MORE FILES, DELAYED ERROR":
                    empty_num = empty_num + 1
                    logging.info("File was empty, if next " + str(
                        5 - empty_num) + " files are empty, next combination will start")
                file_num = file_num + 1
                driver.close()

            logging.info(f'Done processing {year} {list_comb}')
            mark_combo_done(list_comb, parent_raw_html_dir)
        mark_year_done(year)

    driver.quit()
