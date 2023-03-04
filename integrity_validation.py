#!/usr/bin/env python
# coding: utf-8

import os
from pathlib import Path
from glob import glob
import pandas as pd
import tqdm
from PyPDF2 import PdfReader 
from PyPDF2.errors import EmptyFileError
import codecs
import csv
import logging
import argparse
import regex as re
import datetime, textract, olefile
import aspose.words as aw
import win32com.client
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)


CLEANED_DIR = "data_cleaned_sample"
GLOBAL_DIR = "D:/aux_data/amag_scraped_data/"
# INPUT_DIR = "sample_data"
INPUT_DIR = "2022/downloaded_files"
OUTPUT_DIR = "data_reports"
ENCODING = 'utf-8'


def search_regexes(text, regexes):
    for regex in regexes:
        match = re.search(regex, text)
        if match is not None:
            return match.group().strip()
        else:
            return None


def read_doc(file_path):
    try:
        case = aw.Document(file_path)
        case_text = case.get_text()
        return case_text
    except:
        return None


def read_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n" 
        return text
    except:
        return None

    # with open(file_path, 'rb') as file:
    #     txt = (file.readlines())
    # # get the new list terminating correctly
    # txtx = reset_eof_of_pdf_return_stream(txt)
    # # write to new pdf
    # with open(file_path, 'wb') as file:
    #     file.writelines(txtx)
    # pdf = PdfReader(file_path)

    # num_pages = len(pdf.pages)
    # pages = [pdf.pages[index].extract_text() for index in range(num_pages)]
    # file_code_validation = file_code.split("_")[0]
    # text_str = " ".join(pages)


def get_string_ole(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    try_encodings = ['utf-8', 'iso-8859-1', 'cp1252', 'utf-16', 'utf-16le', 'utf-16be', 'windows-1252']
    for encoding in try_encodings:
        try:
            text = data.decode(encoding)
            return text
        except UnicodeDecodeError:
            pass
    raise ValueError('Failed to decode file with all attempted encodings.')


def make_cleaned_data_dir():
    Path(CLEANED_DIR).mkdir(exist_ok=True)

def rename_partially_downloaded_files():
    partial_files = glob('data/**/*.crdownload', recursive=True)
    for filename in partial_files:
        start_index = filename.rindex('/')+1
        new_filename = filename[0:start_index] + 'crdownload_' + filename[start_index:filename.rindex('.')]
        os.rename(filename, new_filename)  # removing .crdownload extension from files, but adding a prefix crdownload_ to such files

# Do not rename partially downloaded files for now
# See: https://github.com/weilu/peru_scrape/pull/19#discussion_r450548597
# rename_partially_downloaded_files()

def parse_args():
    parser = argparse.ArgumentParser(description='Clean & extract data into csv files from scraped files')
    current_year = datetime.datetime.now().year
    parser.add_argument('-y', '--years', dest='years', action='store', type=int,
        nargs='*', choices=list(range(1978, current_year+1)), default=None,
        help='years to scrape, default to all available years in the data folder')
    args = parser.parse_args()
    return args.years

def list_subfolders_with_paths():
    return [f.path for f in os.scandir("data") if f.is_dir()]

if __name__ == '__main__':
    license_path = r"D:\Descargas\Aspose.Total.Product.Family.lic"
    with open(license_path, "rb") as f:
        license = aw.License()
        license.set_license(f)

    year_folders = list_subfolders_with_paths()
    
    for index in [2022]:
        glob_dir = GLOBAL_DIR + INPUT_DIR
        out_dir = GLOBAL_DIR + OUTPUT_DIR
        # test_path = "D:/aux_data/amag_scraped_data/2022/downloaded_files\\00057-2022-97-0107-JP-CI-02_1\\res_2022000570114522000632937.doc"
        # print("demo 1")
        # test_path = r"D:\aux_data\amag_scraped_data\2022\downloaded_files\00033-2022-0-0801-JR-FC-01_4\res_2022000070105037000512387.doc"
        # case = aw.Document(test_path)
        # case_text = case.get_text()
        # test_code = "00007-2022-0-2504-JM-CI-01"
        # regex_str = r"\d*-\d*-\d*-\d*-\d*\w*-\w*-\d*"
        # code_from_text = re.search(regex_str, case_text).group().strip()
        # print("-----------")
        # print("code in file: ", code_from_text)
        # print("test code equality. are they equal?: ", test_code == code_from_text)
        # print("---")
        # print("text: ", case_text)
        #  case.save(r"D:\Accesos directos\Trabajo\World Bank\WB Repos\peru-scrape-justice\data_cleaned_sample\doc-to-text.html")
        
        ## actual working code ###
        list_files = glob(glob_dir + "/**/*.doc", recursive=True)
        list_files += glob(glob_dir + "/**/*.pdf", recursive=True)

        with codecs.open(f"{out_dir}/DF_INTEGRITY_2022.csv", "w", ENCODING) as fp:

            writer = csv.writer(fp)
            writer.writerow(["expediente_num","num", "error","file_path", "extension", "link", "passed_validation", "code_from_file"])

            for index in tqdm.trange(len(list_files)):
            #  for index in tqdm.trange(3):
                file_path = list_files[index]
                file_code = file_path.split("/")[-1].split("\\")[1] # code from folder
                link_file_path = glob_dir + "/" + file_code + "/link.txt"
                
                f = open(link_file_path, "r")
                link = f.read()
                link = link.replace("https://cej.pj.gob.pe/cej/forms/", "")
                
                expediente_num = link_file_path.split("/")[-2].split("_")[0].strip()
                num = link_file_path.split("/")[-2].split("_")[-1]
                
                code_from_text = None
                extension = None
                if ".pdf" in file_path:
                    # pdf_path = r"D:\aux_data\amag_scraped_data\sample_data\00001-2022-0-0101-JP-CI-01_6\res_2022000010093054000993737.pdf"
                    extension = "pdf"
                    text = read_pdf(file_path)
                else: # doc file
                    extension = "doc"
                    text = read_doc(file_path)
                if text != None:
                    code_from_text = search_regexes(text, [r"\d*-\d*-\d*-\d*-\d*\w*-\w*-\d*", r"\d*-\d*-\d*-\w*-\w*-\d*"])
                    passed_validation = "No" # verified if file code in txt
                    if expediente_num==code_from_text:
                        passed_validation = "Yes"
                    writer.writerow([expediente_num, num, "", file_path, extension, link, passed_validation, code_from_text])
                else:
                    writer.writerow([expediente_num, num, "File is unreadable", file_path, extension, link, "", ""])
                # try:
                #     if ".pdf" in file_path:
                #         with open(file_path, 'rb') as file:
                #             txt = (file.readlines())
                #         # get the new list terminating correctly
                #         txtx = reset_eof_of_pdf_return_stream(txt)
                #         # write to new pdf
                #         with open(file_path, 'wb') as file:
                #             file.writelines(txtx)
                #         pdf = PdfReader(file_path)

                #         num_pages = len(pdf.pages)
                #         pages = [pdf.pages[index].extract_text() for index in range(num_pages)]
                #         file_code_validation = file_code.split("_")[0]
                #         text_str = " ".join(pages)
                    # else:
                    #     text_str = getText(file_path)
                    
        #             passed_validation = "No" # verified if file code in txt
        #             if file_code_validation in text_str:
        #                 passed_validation = "Yes"

        #             writer.writerow([expediente_num,num, '', file_path,link, passed_validation])

        #         except (UnicodeDecodeError) as err:
        #             logging.warning("UnicodeDecodeError/ShellError while processing file - " + str(file_path))
        #             logging.exception(err)
        #             writer.writerow([expediente_num,num, str(err), file_path, link,""])
        #         except TypeError as err:
        #           if str(err) == "decode() argument 1 must be str, not None":
        #             logging.warning("TypeError while processing file - " + str(file_path))
        #             logging.exception(err)
        #             writer.writerow([expediente_num,num, str(err), file_path, link,""])
        #           else:
        #             raise err

        #     logging.info("Download files cleaned for 2022 data")

        # logging.info("Download files cleaned for all years, cleaning process completed")

