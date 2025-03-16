#!/usr/bin/python
####################################################################################################################################
# Description:                                                                                                                     #
#               In each dir defined in files_to_exclude.config, exlcude the list of files or file patterns                         #
#               And delete the rest if unmodifeid in last 48 hours                                                                 #
#               Directory deletion logic for /adbadmin                                                                             #
#               1. Any directory with a name starting with 3 or 4 and unmodified in > 365 days is deleted                          #
#               2. All other directories with a name starting with other digits and unmodified in > 30 days are deleted            #
# Test Cases:                                                                                                                      #
#               1. Program wont proceed if files_to_exclude.config doesn't exist under base_path                                   #
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
# Modification History:                                                                                                            #
#               rrsolomo: added all utility functions                                                                              #
#               rrsolomo: added time checks to permit files created < 48 hours to exist                                            #
#               rrsolomo: added config file exception conditions to avoid human errors                                             #
#               rrsolomo: cosmetic changes to logging data                                                                         #
#               rrsolomo: Files modified < 48 hours ago will be retained even when not prsent in exclude list                      #
#               rrsolomo: Added wildcard parsing functionality to exclude files like "tf*.env"                                     #
#               rrsolomo: Added functionality to delete directories older than an year with name starting with digits in /adbadmin #
#               rrsolomo: Enahnced functionality to delete dirs under /adbadmin based on dir name and age                          #
####################################################################################################################################

import configparser
import json
import os
import logging
import datetime
import glob
import shutil

"""
Variable Declaration
"""
sample_config = '''
\t\t\t\t  An example entry in config file would look like \n \t\t\t\t  [DIRECTORY_PATH] \n \t\t\t\t  files = ["1.txt","2.txt"]
'''
seperator1 = "-"*100
delim = "\n\t\t\t\t\t > "

base_path = '/adbadmin/rrsolomo/'
log_file_path = '/adbadmin/rrsolomo/ops_files_purge.log'
dirs_to_del_list = ["/adbadmin/rrsolomo"]

"""
file_path_correction(): Adds a "/" at the end of directory paths. This is to avoid human error while creating the config file
return: file_path
"""
def file_path_correction(file_path):
    if file_path[-1] != "/":
        file_path = file_path+"/"
    return file_path

base_path = file_path_correction(base_path)
config_file = base_path+"ops_files_purge_exceptions.cfg"
logging.basicConfig(filename=log_file_path,level=logging.DEBUG,format='%(asctime)s - %(levelname)-8s - %(message)s')

"""
header_footer(): For cosmetic purpose. Adds line separator in the log file for better readability
return: nothing
"""
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

"""
modification_days_minutes_calculator(): Utility function to compute the modified tim eof a dir and compute the difference in days/hrs/mins with current time
return : diff_days,diff_hrs,diff_mins
"""
def modification_days_minutes_calculator(root):
    modification_time = os.path.getmtime(root)
    modification_date = datetime.datetime.fromtimestamp(modification_time)
    current_date_and_time = datetime.datetime.now()
    diff_days  = round((current_date_and_time - modification_date).total_seconds() / (60 * 60 * 24))
    diff_hrs  = round((current_date_and_time - modification_date).total_seconds() / (60 * 60))
    diff_mins =  round((current_date_and_time - modification_date).total_seconds() / (60))
    return diff_days,diff_hrs,diff_mins

"""
config_file_check(): Parse ops_files_purge_exceptions.cfg file
return: config
"""
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
"""
file_differences(): For each directory path mentioned in ops_files_purge_exceptions.cfg , identify the difference between current files/dirs and
                                        the exclude list. Pass this difference list to delete_files().
return: nothing
"""
def file_differences(config):
    try:
        sections = config.sections()
        if len(sections) !=0:
            for section in sections:
                logging.info('PROCESSING :  %s', section)
                if os.path.isdir(section):
                    try:
                        if (list(config[section].keys())[0]) == 'files':
                            files_to_exclude = json.loads(config.get(section, 'files'))
                            files_to_exclude = [str(file) for file in files_to_exclude]
                            section = file_path_correction(section)
                            section =  section.encode('ascii', 'ignore')
                            current_files = os.listdir(section)
                            if len(files_to_exclude) != 0:
                                wild_card_pattern_found = [str(sub) for sub in files_to_exclude if "*" in sub]
                                if len(wild_card_pattern_found) !=0 :
                                    for pattern in wild_card_pattern_found:
                                        file_list = glob.glob(os.path.join(section+pattern))
                                        file_list2 = [i.split("/")[-1].split("\\")[-1] for i in file_list]
                                        files_to_exclude.extend(file_list2)
                                        files_to_exclude.remove(pattern)

                                if(len(set(current_files).difference(set(files_to_exclude)))) > 0:
                                    difference = list(set(current_files).difference(set(files_to_exclude)))
                                    delete_files(difference,section)
                                else:
                                    logging.info('No files to delete in %s', section)
                                    # logging.info('Current files/directories in directory : %s are \n\t\t\t\t %s', section,  [str(file) for file in os.listdir(section)])
                                    logging.info('%s',seperator1)
                                    logging.info('Current files/directories in directory : %s are: \n\t\t\t\t\t %s', section,  delim.join(list(map(str,os.listdir(section)))))
                                    logging.info('%s',seperator1)
                            else:
                                logging.warning('No files included in the exclude list for directory %s. \n\t\t\t\t\t Any files not modified in the last 48 hours in this directory will be deleted.', section)
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
    except Exception as e:
        logging.error("An error occured when processing file_differences function: %s",str(e))

"""
delete_files(): For each directory path mentioned in ops_files_purge_exceptions.cfg, remove the files identified in difference list
return: nothing
"""
def delete_files(difference,section):
    try:
        deleted_files=[]
        for file in difference:
            if os.path.isfile(section+file):
                diff_days,diff_hrs,diff_mins = modification_days_minutes_calculator(section+file)

                if diff_hrs <= 48:
                    logging.info('File %s was modified in the last 48 hours. Hence its not being deleted', section+file)
                else:
                    deleted_files.append(section+file)
                    os.remove(section+file)
                    logging.info('Deleted file %s', section+file)
            else:
                logging.info('%s is a directory. Hence not deleted', section+file)

        if len(deleted_files)!=0:
            # logging.info('The following files were deleted in this execution: %s', [str(file) for file in deleted_files])
            logging.info('The following files were deleted in this execution: \n\t\t\t\t\t > %s',  delim.join(list(map(str,deleted_files))))
        logging.info('%s',seperator1)
        # logging.info('Current files/directories in directory : %s are \n\t\t\t\t %s', section,  [str(file) for file in os.listdir(section)])
        logging.info('Current files/directories in directory : %s are: \n\t\t\t\t\t > %s', section,  delim.join(list(map(str,os.listdir(section)))))
        logging.info('%s',seperator1)
    except Exception as e:
        logging.error("An error occured when processing delete_files operation: %s",str(e))


"""
dir_del_banner(del_or_nodel_flag,root,no_of_dirs,no_of_files,age_to_print)
Banner message in the log when dir is either deleted or not deleted based on age specification
"""
def dir_del_banner(del_or_nodel_flag,root,no_of_dirs,no_of_files,age_to_print):
    if del_or_nodel_flag == "del":
        logging.info('PROCESSING : %s',root)
        logging.info('%s : has %s directori(es) and %s file(s)', root,no_of_dirs,no_of_files)
        logging.info('%s is  older than %s days. Hence proceeding with deletion of the directory', root,age_to_print) 
    else:
        logging.info('PROCESSING : %s',root)
        logging.info('%s : has %s directori(es) and %s file(s)', root,no_of_dirs,no_of_files)
        logging.info('%s is not older than %s days. Sub-directories will be probed further.',root,age_to_print)
        logging.info('%s',seperator1) 
"""
del_dirs_3_4(root,no_of_dirs,no_of_files,diff_mins)
def del_dirs_not_3_4(root,no_of_dirs,no_of_files,diff_mins)
Both are utility functions called from del_dirs(). While both handle deletion of directories, one deals with directories with anme starting with either 3 or 4
And the other deals with the rest of with name starting with other digits
"""
def del_dirs_3_4(root,no_of_dirs,no_of_files,diff_days):
    if diff_days > 365:
        dir_del_banner("del",root,no_of_dirs,no_of_files,age_to_print=365)
        deleted_dirs.append(root)
        shutil.rmtree(root,ignore_errors=True)
        logging.info('%s',seperator1)
    else:
        dir_del_banner("nodel",root,no_of_dirs,no_of_files,age_to_print=365)

def del_dirs_not_3_4(root,no_of_dirs,no_of_files,diff_days):
    if diff_days > 30:
        dir_del_banner("del",root,no_of_dirs,no_of_files,age_to_print=30)
        deleted_dirs.append(root)
        shutil.rmtree(root,ignore_errors=True)
        logging.info('%s',seperator1)
    else:
        dir_del_banner("nodel",root,no_of_dirs,no_of_files,age_to_print=30)

"""
del_dirs(): Deletes the directories which are older than an year and whos name starts with a digit
STEP 1 : Check if dir name starts with a digit
STEP 2 : If dir name starts either with a "3" or a "4", if unmodified in last 365 days, delete it
STEP 3 : If not older than an year, probe the sub-dirs and check STEP 2
STEP 4 : If dir name starts with any other digit, if unmodified in last 365 days, delete it. Else probe the sub-dirs and check STEP 2
return: nothing
"""
deleted_dirs = []
def del_dirs(src_dir):
    dir_digits=[3,4]    
    for root, dirs, files in os.walk(src_dir):
        diff_days,diff_hrs,diff_mins = modification_days_minutes_calculator(root)
        if root == src_dir:
            continue
        leaf_dir = root.split("/")[-1].split("\\")[-1]
        if leaf_dir[0].isdigit():
            leaf_dir_name = int(leaf_dir[0])
            if leaf_dir_name in dir_digits:
                del_dirs_3_4(root,len(dirs),len(files),diff_days)
            if leaf_dir_name not in dir_digits:
                del_dirs_not_3_4(root,len(dirs),len(files),diff_days)

header_footer("begin")
config = config_file_check()
if config is not None:
    try:
        file_differences(config)
    except OSError as error :
        logging.error('%s', error)
    try:
        logging.info('%s',seperator1)
        logging.info('PROCESSING :  DELETION of directories older than an year under /adbadmin')
        logging.info('%s',seperator1)
        for dir in dirs_to_del_list:
            del_dirs(dir)
        # logging.info('Deleted dir %s', [str(dir) for dir in deleted_dirs])
        if len(deleted_dirs)!=0:
            logging.info('The following directories were deleted in this execution: \n\t\t\t\t\t > %s',  delim.join(list(map(str,deleted_dirs))))
            logging.info('%s',seperator1)
    except Exception as e:
        logging.error("An error occured when processing del_dirs operation: %s",str(e))
header_footer("end")
