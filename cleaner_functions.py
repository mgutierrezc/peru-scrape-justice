#!/usr/bin/env python
# coding: utf-8

from bs4 import BeautifulSoup
import os
import tqdm
import pandas as pd
import numpy as np
from collections import defaultdict


def scrape_data(path_to_html):
    
    """ Function to extract data out of raw_html files"""

    with open(path_to_html, "r") as f:

        contents = f.read()

        soup = BeautifulSoup(contents, 'lxml')


    file_report_tags_list = []
    file_report_values_list = []

    procedural_parts_tags = []

    follow_up_tags_1 = []
    follow_up_tags_2 = []


    
    #reporte_de_expediente  TABLE 1
    tags = []
    values = []
    value_sumilla = []
    

    tags = soup.findAll("div", {"class": "celdaGridN"})
        

    values = soup.findAll("div", {"class": "celdaGrid"})
    

    value_sumilla = soup.findAll("div", {"class": "celdaGridxT"})
    
    tags_text = []
    values_text = []
    
    for index in range(len(tags)):
        tags_text.append(tags[index].text)

    for index in range(len(values)):
        values_text.append(values[index].text)
    
    for index in range(len(value_sumilla)):
        values_text.append(value_sumilla[index].text)
        

    
    
    file_report_tags_list.append(tags_text)
    file_report_values_list.append(values_text)
    
    # Partes Procesales table  Table 2
    tags_pp = []
    

    tags_pp = soup.findAll("div", {"class": "partes"})
        
    tags_pp_text = []
    
    if (len(tags_pp) != 0):
        for index in range(len(tags_pp)):
            tags_pp_text.append(tags_pp[index].text)
        
    procedural_parts_tags.append(tags_pp_text)
        
    
    notification_tables = soup.findAll("div", {"class": "modal-content"})
    notifications_text = []
    
    for index in range(len(notification_tables)):
        notifications_text.append(notification_tables[index].text)
     
    notifications_text_list = []
    notifications_text_list.append(notifications_text)
    
    return file_report_tags_list, file_report_values_list, procedural_parts_tags, notifications_text_list
    

def csv_saver(file_report_tags_list, file_report_values_list, procedural_parts_tags, notifications_text_list):
    
    for index in range(len(file_report_tags_list)):
        
        #print("--"+str(index)+"--")
        file_report = pd.DataFrame()
        procedural_parts = pd.DataFrame()

        notifications = pd.DataFrame()
        
        file_report["Tags"] = pd.Series(file_report_tags_list[index])
        file_report["Values"] = pd.Series(file_report_values_list[index])
        
        procedural_parts["Data"] = pd.Series(procedural_parts_tags[index])
        
        
        if(notifications_text_list != []):
            notifications["Data"] = pd.Series(notifications_text_list[index])
        else:
            notifications["Data"] = None
    
    return file_report, procedural_parts, notifications


def file_report_Cleaner(df1):

    list_file_report = []
    list_file_report = df1["Tags"]  #getting the tags (e.g. Juez, Fecha de Inicio et cetera)
    list_file_report = list_file_report.to_list()


    col_values_file_report = []
    col_values_file_report = df1["Values"]  #getting the values of the tags
    col_values_file_report = col_values_file_report.to_list()


    dict_file_report = dict(zip(list_file_report, col_values_file_report))

    return list_file_report, col_values_file_report, dict_file_report



def procedural_parts_Cleaner(df2):

    list_procedural_parts = []
    list_procedural_parts.append("Parte")

    col_values_procedural_parts = []
    col_values = []
    list_dicts_procedural_parts = []
    list_list_dicts_procedural_parts = []

    if (len(df2) != 0):

        for index in range(len(df2)):
            col_values.append(df2["Data"][index])
    
        col_values_procedural_parts.append(col_values)

        list_vals = []
    
        list_tags = col_values_procedural_parts[0][0].split("\n")

        for index in range(1, len(col_values_procedural_parts[0])):
            list_vals.append(col_values_procedural_parts[0][index].split("\n"))

        
        for i in range(len(list_vals)):
            list_dicts_procedural_parts.append(dict(zip(list_tags, list_vals[i])))
    
        list_list_dicts_procedural_parts.append(list_dicts_procedural_parts)  #list of list of dictionaries
    
 
        dict_procedural_parts = dict(zip(list_procedural_parts, list_list_dicts_procedural_parts))
    
        return list_procedural_parts, col_values_procedural_parts, dict_procedural_parts

    else:
        return [], [], {}
    
    

def procedural_parts_Cleaner_2(list_of_dicts, file_num): # to further clean procedural parts table
    for i in range(len(list_of_dicts)):
        list_of_dicts[i].pop('')
        list_of_dicts[i]["Expediente N°:"] = file_num
    list_dictionary = list_of_dicts
    return list_dictionary


def notifications_cleaner(notification_text, file_name):

 no_selection = ["×", "Destinatario:", "Anexos:", "Fecha de Resolución:", "Notificación Impresa el:", "Enviada a la Central de Notificación o Casilla Electrónica:", "Recepcionada en la central de Notificación el:", "Notificación al destinatario el:", "Cargo devuelto al juzgado el:","Forma de entrega:" ]
 file_num = str(file_name)
 col_values_notifications_list = []

 notification_text_list = notification_text.split("\n")
 notification_text_list = [elem for elem in notification_text_list if elem != ""]
     
 col_values_notifications = []
 col_values_notifications.append(file_num)
     
 for k in range(len(notification_text_list)):
     if(notification_text_list[k] in no_selection):
         if(k < len(notification_text_list)-1):
             if(notification_text_list[k+1] not in no_selection):
                 col_values_notifications.append(notification_text_list[k+1])
             else:
                 col_values_notifications.append(None)
         else:
             col_values_notifications.append(None)
             
 col_values_notifications_list.append(col_values_notifications)
 index = no_selection.index("×")
 no_selection[index] = "Notification:"
 df_notifications = pd.DataFrame(col_values_notifications_list,columns = ["Expediente N°:"] + no_selection)

 return df_notifications
 
 
def follow_up_linker_cleaner(path_to_html):
 
    with open(path_to_html, "r") as f:
        contents = f.read()
        soup = BeautifulSoup(contents, 'lxml')
        
    tab_1 = soup.findAll("div", {"class": "panel panel-default divResolImpar"})
    tab_2 = soup.findAll("div", {"class": "panel panel-default divResolPar"})
    
    tabs = tab_1 + tab_2
    
    dict_links = {}
    dict_flefts = {}
    
    for index in range(len(tabs)):
        links = tabs[index].findAll('a')
        links_href = [ele.get("href") for ele in links if ele.has_attr('href')]
        if(links_href != []):
            dict_links[index] = links_href
        else:
            dict_links[index] = [None]
        flefts = tabs[index].findAll("div", {"class": "fleft"})
        flefts_text = [ele.text for ele in flefts]
        flefts_text = flefts_text[:8]
        dict_flefts[index] = flefts_text
        
    expediente = soup.findAll("div", {"class": "celdaGrid celdaGridXe"})
    expediente_n = expediente[0].text
    
    data_rows_list = []
    
    for index in range(len(tabs)):
        data_row = [expediente_n] + dict_links[index] + dict_flefts[index]
        data_rows_list.append(data_row)
        
    return data_rows_list
