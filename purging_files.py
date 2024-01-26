#!/usr/bin/python
####################################################################################################################################
# Description:                                                                                                                     #
#               Code to remove files defined under each section which trasnlates to dirs in ops_files_purge_exceptions.config.     #
# Test Cases:                                                                                                                      #
#               1. Program wont proceed if ops_files_purge_exceptions.config doesn't exist under base_path                         #
#               2. file_path_correction() adds a "/" incase base_path or section defined in                                        #
#                  config file doesnt have "/" as the last character                                                               #
#               3. If no files satisfy DELETE condition, the same is logged in app.log                                             #
#               4. If any file is DELETED, the same is logged in app.log                                                           #
#               5. If the file to be deleted is a directory, it wont be deleted and same is logged in app.log                      #
#               6. After each operation, files in current directory that is each section in the config file are printed in app.log #
#               7. If no values are provided for any section thats is directory path, same will be logged.                         #
#                  Without this check it would delete all files under that directory                                               #
#               8. If files's age is < 48 hours, they wont be deleted                                                              #
#               9. Exception conditions for config file parsing including:                                                         #
#                  a. Config file is empty                                                                                         #
#                  b. Section = Directory in config file doesnt exist                                                              #
#                  c. Incorrect key in section. Expected key is "Files"                                                            #
#                  d. Empty list of "files"                                                                                        #
# Modificatin History:                                                                                                             #
#               theowl: added all utility functions                                                                                #
#               theowl: added time checks to permit files created < 48 hours to exist                                              #
#               theowl: added config file exception conditions to avoid human errors                                               #
#               theowl: cosmetic changes to logging data                                                                           #
#               theowl: Files modified < 48 hours ago will be retained even when not prsent in exclude list                        #
#               theowl: Added wildcard parsing functionality to exclude files like "tf*.env"                                       #
####################################################################################################################################

import configparser
import json
import os
import logging
import datetime
import glob

sample_config = '''
\t\t\t\t  An example entry in config file would look like \n \t\t\t\t  [DIRECTORY_PATH] \n \t\t\t\t  files = ["1.txt","2.txt"]
'''
base_path = '/ops/scripts/'
log_file_path = '/tmp/ops_files_purge.log'

def file_path_correction(file_path):
    if file_path[-1] != "/":
        file_path = file_path+"/"
    return file_path

base_path = file_path_correction(base_path)
config_file = base_path+"ops_files_purge_exceptions.cfg"

logging.basicConfig(filename=log_file_path,level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def header_footer(state):
    seperator = "="*100
    if state == "begin":    
        logging.info('%s',seperator)
        logging.info('Log for operations performed on %s', datetime.datetime.now())
        logging.info('%s',seperator)
    else:
        logging.info('%s',seperator)
        logging.info('End of operations performed on %s', datetime.datetime.now())
        logging.info('%s',seperator)

def config_file_check():
    try:            
        if os.path.exists(config_file):
            config = configparser.ConfigParser()
            config.read(config_file)        
            return config
        else:
            logging.error('File ops_files_purge_exceptions.cfg doesnt exist in %s', base_path)
    except (ValueError, configparser.MissingSectionHeaderError, configparser.DuplicateSectionError, configparser.DuplicateOptionError,configparser.ParsingError) as e:
        logging.error("An error occured when loading ops_files_purge_exceptions.cfg: %s",str(e))
        logging.error("Try adding atleast one directory path. %s", sample_config)

def file_differences(config):
    sections = config.sections()
    if len(sections) !=0: 
        for section in sections:
            logging.info('Processing :  %s', section)
            if os.path.isdir(section):
                try:
                    if (list(config[section].keys())[0]) == 'files':           
                        files_to_exclude = json.loads(config.get(section, 'files'))
                        section = file_path_correction(section)
                        current_files = os.listdir(section)
                        if len(files_to_exclude) != 0:
                            files_to_exclude = processing_files_with_wildcard(section,files_to_exclude)
                            if(len(set(current_files).difference(set(files_to_exclude)))) > 0:
                                difference = list(set(current_files).difference(set(files_to_exclude)))
                                print("difference:::",difference)
                                delete_files(difference,section)
                            else:
                                logging.info('No files to delete in %s', section)
                                logging.info('Current files/directories in directory : %s are \n\t\t\t\t %s', section,  [str(file) for file in os.listdir(section)])
                        else:
                            logging.warning('No files included in the exclude list for directory %s. Any files not modified in the last 48 hours in this directory will be deleted.', section)
                            difference = list(set(current_files).difference(set(files_to_exclude)))
                            delete_files(difference,section)
                    else: 
                        logging.error('Invalid key found for directory path: %s in ops_files_purge_exceptions.cfg. Expected "files" found "%s"', section, list(config[section].keys())[0],)
                        logging.error("Correct the key. %s", sample_config)
                except Exception as e:
                        logging.error("An error occured when parsing the ops_files_purge_exceptions.cfg: %s",str(e))
                        logging.error("Check the values defined for %s.", section)
                        logging.error("Check the configuration details. %s", sample_config)
            else: 
                logging.warning('Directory path %s mentioned in ops_files_purge_exceptions.cfg doesnt exist', section)
    else:
        logging.warning('File ops_files_purge_exceptions.cfg is empty')

def delete_files(difference,section):
    deleted_files=[]
    for file in difference:
        if os.path.isfile(section+file):          
            modification_time = os.path.getmtime(section+file)
            modification_date = datetime.datetime.fromtimestamp(modification_time)
            current_date_and_time = datetime.datetime.now()
            diff_hrs  = round((current_date_and_time - modification_date).total_seconds() / (60 * 60 ))
            diff_mins  = round((current_date_and_time - modification_date).total_seconds() / (60))
            if diff_hrs <= 48: 
                logging.info('File %s was modified in the last 48 hours. Hence its not being deleted', section+file)
            else:
                deleted_files.append(section+file)
                os.remove(section+file)
                logging.info('Deleted file %s', section+file)
        else:
            logging.info('%s is a directory. Hence not deleted', section+file)

    if len(deleted_files)!=0:
        logging.info('The following files were deleted in this execution: %s', [str(file) for file in deleted_files])
    logging.info('Current files/directories in directory : %s are \n\t\t\t\t %s', section,  [str(file) for file in os.listdir(section)])

def processing_files_with_wildcard(section,files_to_exclude):
    pattern = "db*.py"
    file_list = glob.glob(section+pattern)
    # file_list2 = [i.strip(section).strip("\\")+"py" for i in file_list]
    file_list2 = [i.split("/")[-1].strip("\\") for i in file_list]
    files_to_exclude.extend(file_list2)
    return files_to_exclude

header_footer("begin")
config = config_file_check()
if config is not None:
    try:
        file_differences(config)
    except OSError as error :
        logging.error('%s', error)
header_footer("end")