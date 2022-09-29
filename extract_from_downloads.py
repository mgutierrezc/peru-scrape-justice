#!/usr/bin/env python
# coding: utf-8

import textract
import os
from pathlib import Path
from glob import glob
import pandas as pd
import re
import tqdm
import codecs
import csv
import logging
import traceback
from textract.exceptions import ShellError
import argparse
import datetime
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)



CLEANED_DIR = "data_cleaned"
ENCODING = 'utf-8'


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
    years = parse_args()
    make_cleaned_data_dir()

    year_folders = list_subfolders_with_paths()
    
    for index in range(len(year_folders)):
        year = re.findall("\d+", year_folders[index])[0]
        if years and int(year) not in years:
            continue

        logging.info("Starting cleaning download files for year - " + str(year))
        glob_dir = str(year_folders[index])
        list_files = glob(glob_dir + "/**/*.doc", recursive=True)
        list_files += glob(glob_dir + "/**/*.pdf", recursive=True)
        

        with codecs.open(f"{CLEANED_DIR}/DF_DOWNLOADS_{year}.csv", "w", ENCODING) as fp:

            writer = csv.writer(fp)
            writer.writerow(["expediente_num","num","text", "error","file_path", "link"])

            for index in tqdm.trange(len(list_files)):
                file_path = list_files[index]
                link_file_path = "/".join(ele for ele in file_path.split("/")[:-1]) + "/link.txt"
                
                f = open(link_file_path, "r")
                link = f.read()
                link = link.replace("https://cej.pj.gob.pe/cej/forms/", "")
                
                expediente_num = link_file_path.split("/")[-2].split("_")[0]
                num = link_file_path.split("/")[-2].split("_")[-1]
                
                try:
                    text = textract.process(file_path, encoding=ENCODING, method='pdfminer')
                    text_str = text.decode(ENCODING)
                    writer.writerow([expediente_num,num,text_str, '', file_path,link])

                except (UnicodeDecodeError, ShellError) as err:
                    logging.warning("UnicodeDecodeError/ShellError while processing file - " + str(file_path))
                    logging.exception(err)
                    writer.writerow([expediente_num,num,'', str(err), file_path, link])
                except TypeError as err:
                  if str(err) == "decode() argument 1 must be str, not None":
                    logging.warning("TypeError while processing file - " + str(file_path))
                    logging.exception(err)
                    writer.writerow([expediente_num,num,'', str(err), file_path, link])
                  else:
                    raise err


            logging.info("Download files cleaned for year - " + str(year))

        logging.info("Download files cleaned for all years, cleaning process completed")

