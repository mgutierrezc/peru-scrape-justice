#!/usr/bin/env python
# coding: utf-8

import os
from pathlib import Path
from glob import glob
import pandas as pd
import tqdm
import codecs
import csv
import logging
import argparse
import datetime
from PyPDF2 import PdfReader
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)


CLEANED_DIR = "data_cleaned_sample"
# INPUT_DIR = "sample_data"
INPUT_DIR = "2022\downloaded_files"
ENCODING = 'utf-8'

def reset_eof_of_pdf_return_stream(pdf_stream_in:list):
    # find the line position of the EOF
    for i, x in enumerate(txt[::-1]):
        if b'%%EOF' in x:
            actual_line = len(pdf_stream_in)-i
            print(f'EOF found at line position {-i} = actual {actual_line}, with value {x}')
            break

    # return the list up to that point
    return pdf_stream_in[:actual_line]

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
    # years = parse_args()
    # make_cleaned_data_dir()

    year_folders = list_subfolders_with_paths()
    
    for index in [2022]:
        glob_dir = "D:/Accesos directos/Trabajo/World Bank/WB Repos/peru-scrape-justice/data/" + INPUT_DIR
        list_files = glob(glob_dir + "/**/*.doc", recursive=True)
        list_files += glob(glob_dir + "/**/*.pdf", recursive=True)
        print("glob_dir: ", glob_dir)
        print("num_files: ", len(list_files))

        with codecs.open(f"{CLEANED_DIR}/DF_INTEGRITY_2022.csv", "w", ENCODING) as fp:

            writer = csv.writer(fp)
            writer.writerow(["expediente_num","num", "error","file_path", "link", "passed_validation"])

            for index in tqdm.trange(len(list_files)):
                file_path = list_files[index]
                file_code = file_path.split("/")[-1].split("\\")[1]
                link_file_path = glob_dir + "/" + file_code + "/link.txt"
                print("file path: ", file_path)

                f = open(link_file_path, "r")
                link = f.read()
                link = link.replace("https://cej.pj.gob.pe/cej/forms/", "")
                
                expediente_num = link_file_path.split("/")[-2].split("_")[0]
                num = link_file_path.split("/")[-2].split("_")[-1]

                try:
                    pdf = PdfReader(file_path)
                    num_pages = len(pdf.pages)
                    pages = [pdf.pages[index].extract_text() for index in range(num_pages)]
                    file_code_validation = file_code.split("_")[0]
                    text_str = " ".join(pages)
                    
                    passed_validation = "No" # verified if file code in txt
                    if file_code_validation in text_str:
                        passed_validation = "Yes"

                    writer.writerow([expediente_num,num, '', file_path,link, passed_validation])

                except (UnicodeDecodeError) as err:
                    logging.warning("UnicodeDecodeError/ShellError while processing file - " + str(file_path))
                    logging.exception(err)
                    writer.writerow([expediente_num,num, str(err), file_path, link,""])
                except TypeError as err:
                  if str(err) == "decode() argument 1 must be str, not None":
                    logging.warning("TypeError while processing file - " + str(file_path))
                    logging.exception(err)
                    writer.writerow([expediente_num,num, str(err), file_path, link,""])
                  else:
                    raise err

            logging.info("Download files cleaned for 2022 data")

        logging.info("Download files cleaned for all years, cleaning process completed")

