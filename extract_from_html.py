#!/usr/bin/env python
# coding: utf-8

from bs4 import BeautifulSoup
import os
import tqdm
import pandas as pd
import numpy as np
from collections import defaultdict
import codecs
import csv
import re
from glob import glob
from cleaner_functions import *
from extract_from_downloads import make_cleaned_data_dir, parse_args, list_subfolders_with_paths

import logging
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO)

ENCODING = "utf-8"

def extract(year, html_paths):
    with codecs.open(f"data_cleaned/DF_file_report_{year}.csv", "w", ENCODING) as f_file_report, \
         codecs.open(f"data_cleaned/DF_procedural_parts_{year}.csv", "w", ENCODING) as f_procedural_parts, \
         codecs.open(f"data_cleaned/DF_follow_up_cleaner_{year}.csv", "w", ENCODING) as f_follow_up_linker, \
         codecs.open(f"data_cleaned/DF_notifications_{year}.csv", "w", ENCODING) as f_notifications:

        # write file headers
        report_writer = csv.writer(f_file_report)
        col_row_file_report = ['Expediente N°:','Órgano Jurisdiccional:','Distrito Judicial:','Juez:','Especialista Legal:',
         'Fecha de Inicio:','Proceso:','Observación:','Especialidad:','Materia(s):','Estado:', 'Etapa Procesal:',
         'Fecha Conclusión:','Ubicación:','Motivo Conclusión:','Sumilla:']
        report_writer.writerow(col_row_file_report)

        procedural_writer = csv.writer(f_procedural_parts)
        col_row_procedural_parts = ['Expediente N°:','Parte','Tipo dePersona','Apellido Paterno /Razón Social','ApellidoMaterno','Nombres']
        procedural_writer.writerow(col_row_procedural_parts)


        notification_writer = csv.writer(f_notifications)
        col_row_notifications = ['Expediente N°:','Notification:','Destinatario:','Anexos:','Fecha de Resolución:','Notificación Impresa el:',
         'Enviada a la Central de Notificación o Casilla Electrónica:','Recepcionada en la central de Notificación el:',
         'Notificación al destinatario el:','Cargo devuelto al juzgado el:','Forma de entrega:']
        notification_writer.writerow(col_row_notifications)
        
        follow_up_linker_writer = csv.writer(f_follow_up_linker)
        col_row_follow_up_linker = ['Expediente N°:','link', 'Fecha de Resolución/Ingreso:', 'Resolución:', 'Tipo de Notificación:',
        'Acto:', 'Fojas/Folios:', 'Proveido:', 'Sumilla:', 'Descripción de Usuario:']
        follow_up_linker_writer.writerow(col_row_follow_up_linker)

        for index in tqdm.trange(len(html_paths)):
            path = str(html_paths[index])
            code = path.split("/")[-1].replace(".txt", "")  #extracting the name of the raw_html file (Expediente N)
            file_report_tags_list, file_report_values_list, procedural_parts_tags, notifications_text_list = scrape_data(path)
            file_report, procedural_parts, notifications = csv_saver(file_report_tags_list, file_report_values_list, procedural_parts_tags, notifications_text_list)
            
            # follow_up_linker_cleaner
            
            data_rows = follow_up_linker_cleaner(path)
            
            for row in data_rows:
                follow_up_linker_writer.writerow(row)

            #file_report cleaner
            list_dict_file_report = []

            list_file_report, col_values_file_report, dict_file_report = file_report_Cleaner(file_report)
            list_dict_file_report.append(dict_file_report)  # making a list of dictionaries to be converted to a dataframe

            DF_file_report_sample = pd.DataFrame([list_dict_file_report[0]])
            DF_file_report_sample = DF_file_report_sample[col_row_file_report]

            rows = DF_file_report_sample.values.tolist()
            for row in rows:
                report_writer.writerow(row)


            # procedural_parts Cleaner
            file_name = code
            list_procedural_parts, col_values_procedural_parts, dict_procedural_parts = procedural_parts_Cleaner(procedural_parts)
            DF_procedural_parts_sample = pd.DataFrame([dict_procedural_parts])

            DF_procedural_parts_sample["Expediente N°:"] = file_name

            grand_list_dicts_2 = []
            for index in range(len(DF_procedural_parts_sample)): # to further clean the procedural_parts table
                list_dictionary = procedural_parts_Cleaner_2(DF_procedural_parts_sample["Parte"][index],DF_procedural_parts_sample["Expediente N°:"][index])
                for j in range(len(list_dictionary)):
                    grand_list_dicts_2.append(list_dictionary[j])

            DF_procedural_parts_sample_v2 = pd.DataFrame([grand_list_dicts_2[0]])

            for i in range(1, len(grand_list_dicts_2)):
                DF_procedural_parts_sample_v2 = DF_procedural_parts_sample_v2.append(grand_list_dicts_2[i],ignore_index=True)

            col_name = "Expediente N°:"
            first_col = DF_procedural_parts_sample_v2.pop(col_name)
            DF_procedural_parts_sample_v2.insert(0, col_name, first_col)

            DF_procedural_parts_sample_v2 = DF_procedural_parts_sample_v2[col_row_procedural_parts]

            rows = DF_procedural_parts_sample_v2.values.tolist()
            for row in rows:
                procedural_writer.writerow(row)



            # Cleaning Notifications Tables:
            if(len(notifications) != 0):
                list_notifications_df = []
                for k in range(len(notifications)):  # Making the new notifications table
                    df = notifications_cleaner(notifications["Data"][k], code)
                    list_notifications_df.append(df)

                DF_notifications_sample = pd.concat(list_notifications_df, axis = 0)
                DF_notifications_sample = DF_notifications_sample[col_row_notifications]

                rows = DF_notifications_sample.values.tolist()
                for row in rows:
                    notification_writer.writerow(row)
                    



if __name__ == '__main__':
  
    years = parse_args()
    make_cleaned_data_dir()

    year_folders = list_subfolders_with_paths()

    for index in range(len(year_folders)):
        year = re.findall("\d+", year_folders[index])[0]
        if years and int(year) not in years:
            continue

        logging.info(f"Starting cleaning HTML files for year {year}")
        html_paths = glob(str(year_folders[index]) + "/**/raw_html/**/*.txt", recursive=True)
        extract(year, html_paths)
        logging.info(f"Done Processing Raw HTMLs for year {year}")

    logging.info("Cleaning Finished")
