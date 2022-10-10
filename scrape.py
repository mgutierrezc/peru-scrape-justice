#!/usr/bin/env python
# coding: utf-8

#importing relevant libraries
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException,\
    StaleElementReferenceException, WebDriverException,\
    ElementNotInteractableException, ElementClickInterceptedException
from selenium.webdriver.common.by import By


import time
import pandas as pd
import re
import numpy as np
import datetime
# FOR CAPTCHA
from PIL import Image
import cv2
import matplotlib.pyplot as plt
#FOR SAVING
import os
from selenium.webdriver.common.keys import Keys
import random
import base64
import io
import pandas as pd

from constants import list_all_comb
import subprocess
from pathlib import Path
import argparse
import shutil
import logging
import string
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)

LINK = 'https://cej.pj.gob.pe/cej/forms/busquedaform.html'
PLACEHOLDER_TEXT = "--SELECCIONAR"
DONE_FLAG = "NO MORE FILES"

#This function cross checks if the element we want to extract exists or not
#not using this will result in errors
def is_element_present(by,value):
    try:
        driver.find_element(by=by, value=value)
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        return False
    return True


# Captcha_Solver
#This function solves for the captcha using OpenCV and Tesseract
def get_captcha_text():
    img_grey = cv2.imread('captcha/screenshot.png', cv2.IMREAD_GRAYSCALE)
    thresh = 128
    img_binary = cv2.threshold(img_grey, thresh, 255, cv2.THRESH_BINARY)[1]
    #imgplot = plt.imshow(img_binary)
    #plt.show()

    kernel = np.ones((3,3), np.uint8)

    img_erosion = cv2.erode(img_binary, kernel, iterations=1)
    #imgplot = plt.imshow(img_erosion)
    #plt.show()

    img_dilation = cv2.dilate(img_erosion, kernel, iterations=1)
    #imgplot = plt.imshow(img_dilation)
    #plt.show()

    cv2.imwrite("captcha/screenshot.png",img_dilation)
    path = Path(__file__).parent / "demo.py"

    cmd = f'{path} --Transformation TPS --FeatureExtraction ResNet --SequenceModeling BiLSTM --Prediction Attn --image_folder captcha/ --saved_model TPS-ResNet-BiLSTM-Attn.pth'
    out = subprocess.Popen(cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=True)
    output, _ = out.communicate()
    list_out = output.decode("ISO-8859-1").strip().split('\n')
    if(list_out != []):
        captcha_text_fin = list_out[-1].split('\t')[1].strip()
        print("captcha_text_fin: ", captcha_text_fin)

    else:
        logging.info("Error occured in Captcha Solving BiLSTM Attention Model")
        return scraper(file_num, list_comb, year, link)

    return captcha_text_fin


def get_captcha_text_via_utterance_text(driver):
    driver.find_element_by_xpath('//*[@id="btnReload"]').click()
    time.sleep(5)
    hidden_text_value = driver.find_element_by_id('1zirobotz0').get_attribute('value')
    return hidden_text_value


def scrape_data():  #to scrape the insides of the site

    button_list = []   #To scrape the button type links of the documents
    try:
        button_list = driver.find_elements_by_xpath('//div[@class="celdCentro"]/form/button')
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
        logging.info("Error occured in getting button links, restarting scraping from the current file number")
        raise RuntimeError("Error Occured")

    table_html = []
    case_names_list = []
    
    if(button_list == []):
        no_files_flag =  True
    else:
        no_files_flag =  False
        
    for index in range(len(button_list)):

        logging.info("--"+str(index)+"--")     # This will tell you which doc is being processed


        # wait 10 seconds before looking for element
        try:
            element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[@class="celdCentro"]/form/button')))
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
            logging.info("Error occured in getting button links, restarting scraping from the current file number")
            raise RuntimeError("Error Occured")

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
                    return (None, None, None)
        #############################################################################################################


        html = driver.page_source
        table_html.append(html)

        #driver.execute_script("var scrollingElement = (document.scrollingElement || document.body);scrollingElement.scrollTop = scrollingElement.scrollHeight;")

        if is_element_present("xpath",'//div[@class="celdaGrid celdaGridXe"]'):
            tags = driver.find_elements_by_xpath('//div[@class="celdaGrid celdaGridXe"]')
        else:
            logging.info("Error occured, restarting scraping from the current file number")
            raise RuntimeError("Error Occured")

        for index in range(len(tags)):
            case_names_list.append(tags[index].text)


        # for downloading the documents

        elements_doc = []

        try:
            if is_element_present("xpath",'//div[@class="panel panel-default divResolPar"]'):
                elements_doc = driver.find_elements_by_class_name("aDescarg")
                expediente_n = driver.find_element_by_class_name("celdaGrid.celdaGridXe").text
                expediente_year = expediente_n.split("-")[1]
                
                existing_faulty_files = os.listdir(faulty_downloads_dir)
                expediente_downloads_file = str(expediente_n) + ".txt"
            
                if(expediente_downloads_file in existing_faulty_files):
                    continue
                    
                for i in range(len(elements_doc)):
            
                    subfolder = str(expediente_n) + "_" + str(i+1)
                
                    attributeValue_link = elements_doc[i].get_attribute("href")

                    target_download_dir = os.path.join('data', expediente_year, 'downloaded_files', subfolder)
                
                    if not os.path.exists(target_download_dir):
                        p = Path(target_download_dir)
                        p.mkdir(parents=True)
                    
                
                    driver.get(attributeValue_link)
                
                    link_path = target_download_dir + "/link.txt"
                
                    with open(link_path, "w+") as f:
                        f.write(str(attributeValue_link))
                        
                    f.close()
                
                    temp_downloads_dir = default_download_path
                    timeout_time = 10  #wait at max 10 seconds for a file to download
                    download_wait(temp_downloads_dir, timeout_time, False)
                
                    file_names = os.listdir(temp_downloads_dir)

                
                    if (file_names !=[]):
                        temp_file_path = os.path.join(temp_downloads_dir, file_names[0])
                        shutil.move(temp_file_path, target_download_dir)
                        logging.info("downloaded")
                            
                    else:
                        logging.info("file not downloaded, will retry")
                        success = retry_download(attributeValue_link, 4, target_download_dir)
                    
                        if not success:
                            faulty_downloads_path = f'{faulty_downloads_dir}/{expediente_n}.txt'
                            Path(faulty_downloads_path).touch()
                   
                   
                    
              
        except (TimeoutException, StaleElementReferenceException,WebDriverException) :
            logging.info("Error occured in getting links of download files, restarting scraping from the current file number")
            raise RuntimeError("Error Occured")
            
        finally:
            element_back = "https://cej.pj.gob.pe/cej/forms/resumenform.html"
            driver.get(element_back)

    return table_html, case_names_list, no_files_flag



# This function saves the extracted data in CSV format
def html_saver(case_names_list, path, table_html):
    parent_dir = str(path) + "/"
    for index in range(len(table_html)):

        logging.info("--"+str(index)+"--")

        file = str(case_names_list[index]) + ".txt"

        with open(os.path.join(parent_dir, file), 'w') as fp:
            fp.write(table_html[index])


# For entering the site and scraping everything inside
# This is the master function
# Please do not tamper with the sleep timers anywhere in this code
def scraper(file_num, list_comb, year):
        driver.get(LINK)
        #driver.maximize_window()
        # wait 10 seconds before looking for element
        try:
            element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'distritoJudicial'), PLACEHOLDER_TEXT))

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

            element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'organoJurisdiccional'), PLACEHOLDER_TEXT))

            # Selecting instance of the case as JUZGADO DE PAZ LETRADO
            select = Select(driver.find_element_by_id('organoJurisdiccional'))
            select.select_by_visible_text(str(list_comb[1]))

            # Civil inside JUZGADO DE PAZ LETRADO

            # wait 10 seconds before looking for element
            element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'especialidad'), PLACEHOLDER_TEXT))

            select = Select(driver.find_element_by_id('especialidad'))
            select.select_by_visible_text(str(list_comb[2]))   # Set to civil, can be changed to any other type depending on the requirements of the user

            #input 1 as case file
            inputElement = driver.find_element_by_id("numeroExpediente")
            inputElement.send_keys(file_num)

            #driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.HOME)
            driver.execute_script("var scrollingElement = (document.scrollingElement || document.body);scrollingElement.scrollTop = scrollingElement.scrollHeight;")

            #finding captcha image
            #find part of the page you want image of
            # image = driver.find_element_by_id('captcha_image').screenshot_as_png
            # screenshot = Image.open(io.BytesIO(image))
            # screenshot.save("captcha/screenshot.png")

            # captcha_text = get_captcha_text()
            captcha_text = get_captcha_text_via_utterance_text(driver)
            captcha_text = ''.join(e for e in captcha_text if e.isalnum())
            captcha = driver.find_element_by_id('codigoCaptcha')
            captcha.clear()

            captcha.send_keys(captcha_text)
            driver.find_element_by_xpath('//*[@id="consultarExpedientes"]').click()

        except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException) as e:
            print({"debug_scraper": e})
            logging.error("Error occured while filling details from list_comb on the first page. Exiting...")
            exit(2)

        text = ''
        text_2 = ''

        time.sleep(2)

        if is_element_present('id', 'codCaptchaError'):
            element_1 = driver.find_element_by_id("codCaptchaError")
            text = element_1.text

        if is_element_present('id', 'mensajeNoExisteExpedientes'):
            element_2 = driver.find_element_by_id("mensajeNoExisteExpedientes")
            text_2 = element_2.text

        if(text_2 == ''):
            if(text == ''):
                parent_dir = get_parent_raw_html_dir(year)
                directory = "_".join(list_comb + ["file_num", str(file_num)])
                path = os.path.join(parent_dir, directory)
                if not os.path.exists(path):
                    Path(path).mkdir(parents=True)
                try:
                    logging.info(f'processing file_num: {file_num}')
                    table_html, case_names_list, no_files = scrape_data()
                except RuntimeError:
                    return scraper(file_num,list_comb,year)
                
                if table_html is None and case_names_list is None:
                    logging.warning(f"Failed to click form button, restarting file_num {file_num}")
                    return scraper(file_num,list_comb,year)
                    
                if(no_files):
                    logging.info("NO MORE FILES, DELAYED ERROR")
                    flag = "NO MORE FILES, DELAYED ERROR"
                    return flag
                else:
                    html_saver(case_names_list, path, table_html)
                    
                mark_combo_file_num_done(list_comb, file_num, parent_dir)
                combo_flag = "Combo Done"
                return combo_flag
            else:
                logging.error("Error, captcha solved incorrectly, retrying")  # IT WILL BE PRINTED WHENEVER WE ENTER THE WRONG CAPTCHA, NO NEED TO WORRY
                time.sleep(2)
                return scraper(file_num,list_comb,year)   # VERY IMPORTANT, RECURSIVELY CALLING THE FUNCTION UNTIL WE GET THE CORRECT CAPTCHA

        else:
            logging.info(f"NO MORE FILES for {list_comb}")
            return DONE_FLAG


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
        logging.error('ERROR: Pre-trained data model for captcha missing or incomplete. Try executing `git lfs pull` if your initial clone did not fetch this file.')
        exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description='Scrape course case data from https://cej.pj.gob.pe/cej/forms/busquedaform.html')
    current_year = datetime.datetime.now().year
    parser.add_argument('-y', '--years', dest='years', action='store', type=int,
        nargs='*', choices=list(range(2019, current_year+1)), default=None,
        help='years to scrape, default to 2019')
    parser.add_argument('-l' '--locations', dest='locations', action='store', type=str,
        nargs='*', choices=list(c[0] for c in list_all_comb), default=None,
        help='locations to scrape, default to all')
    args = parser.parse_args()
    return args.locations, args.years


def get_chrome_options(year=2019):
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
    driver = webdriver.Chrome(executable_path="C:\\chromedriver_win32\\chromedriver.exe", options=get_chrome_options())
    driver.get(LINK)
    element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'distritoJudicial'), PLACEHOLDER_TEXT))
    loc_dropdown = Select(driver.find_element_by_id('distritoJudicial'))
    locations = set(option.text for option in loc_dropdown.options)
    locations.remove(PLACEHOLDER_TEXT)
    return locations


def get_all_valid_years():
    driver = webdriver.Chrome(executable_path="C:\\chromedriver_win32\\chromedriver.exe",options=get_chrome_options())
    driver.get(LINK)
    element = WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'anio'), PLACEHOLDER_TEXT))
    loc_dropdown = Select(driver.find_element_by_id('anio'))
    years = set(option.text for option in loc_dropdown.options)
    years.remove(PLACEHOLDER_TEXT)
    return sorted([int(y) for y in years], reverse=True)


def retry_download(link, max_tries, target_download_dir):

    attr_link = link
    tries = 1
    timeout_time = 10  #wait at max 10 seconds for a file to download
    success = False

    while(tries<max_tries and not success):
        driver.get(attr_link)
        download_wait(default_download_path, timeout_time, False)
        file_names = os.listdir(default_download_path)

        if (file_names !=[]):
            temp_file_path = os.path.join(default_download_path, file_names[0])
            shutil.move(temp_file_path, target_download_dir)
            logging.info("downloaded on try : " + str(tries))
            success = True

        else:
            logging.info("file not downloaded on try " + str(tries) + " ," + str(max_tries-tries) + " left")
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
    
letters = string.ascii_lowercase
random_string = ''.join(random.choice(letters) for i in range(10))
global default_download_path
default_download_path = os.path.join('downloads_temp_' + random_string, 'downloaded_files')

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
                logging.warning(f'Skipping {list_comb} as {list_comb[0]} is not found in the current location dropdown menu')
                continue

            logging.info(f'Start processing {year} {list_comb}')
            file_num = 1 # reset case number to start from 1 for each location-court-type combo
            flag = ""
            empty_num = 0
            
            while(flag != DONE_FLAG and empty_num < 5):
                if is_combo_file_num_done(list_comb, file_num, parent_raw_html_dir):
                    logging.info(f"Already done. Skipping {list_comb} {file_num}")
                    file_num = file_num + 1
                    continue
                try:
                    driver = webdriver.Chrome(executable_path="C:\\chromedriver_win32\\chromedriver.exe",options=get_chrome_options(year))
                except (NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException):
                    logging.info("Error occured in opening Chrome, restarting scraping from the current file number")
                    continue  # not increasing file num by one so that we start again from the same file number in case of an error
                    
                flag = scraper(file_num, list_comb, year)
                if(flag == "NO MORE FILES, DELAYED ERROR"):
                    empty_num = empty_num + 1
                    logging.info("File was empty, if next " + str(5 - empty_num) + " files are empty, next combination will start")
                file_num = file_num + 1
                driver.close()

            logging.info(f'Done processing {year} {list_comb}')
            mark_combo_done(list_comb, parent_raw_html_dir)
        mark_year_done(year)
