#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Zero-touch enrollment quickstart sample.

This script forms the quickstart introduction to the zero-touch enrollemnt
customer API. To learn more, visit https://developer.google.com/zero-touch
"""
from datetime import datetime, timedelta

import gspread
import logging
import json
import pandas as pd
import yaml
import argparse

from typing import List
from pathlib import Path
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.files import GoogleDriveFile
from pandas.core.frame import DataFrame

__doc__ = "Convert an Excel sheet to JSON."

# A single auth scope is used for the zero-touch enrollment customer API.
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

# Define logger
log = logging.getLogger("gsheet-to-json")
logging.basicConfig(level=logging.DEBUG)


class GDriveAgendaHelper:

    def __init__(self, config):
        self.pngs = []
        self.svgs = []
        self.data = []
        self.df = None
        self.scopes = SCOPES
        self.gs_client = None
        self.gs_spreadsheet = None
        self.gs_data_sheet = None
        self.gs_config_sheet = None
        self.gd_client = None
        self.config = config

    def connect(self):
        """
        This function creates a Google Sheets and a Google Drive client, both stored for later usage.
        Authentication relies on Service Accounts and API Tokens
        """
        # Connect to Google API using Service Account using  Bearer Token
        gs_client = gspread.service_account(filename=self.config['sheets']['service_account_key'], scopes=self.scopes)
        self.gs_client = gs_client
        # Access Spreadsheet, Load Worksheets
        gs_spreadsheet = self.gs_client.open_by_key(self.config['sheets']['spreadsheet_id'])
        self.gs_spreadsheet = gs_spreadsheet
        gs_data_sheet = gs_spreadsheet.worksheet(self.config['sheets']['data']['worksheet_id'])
        self.gs_data_sheet = gs_data_sheet
        gs_config_sheet = gs_spreadsheet.worksheet(self.config['sheets']['config']['worksheet_id'])
        self.gs_config_sheet = gs_config_sheet

        # Connect to Google DRIVE API using Service Account using  Bearer Token
        gauth = GoogleAuth()
        gauth.auth_method = 'service'
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            filename=self.config['drive']['service_account_key'],
            scopes=SCOPES)
        self.gd_client = GoogleDrive(gauth)

    def fetch_data(self):
        """
        This function connects to Google Sheets and returns values inside the WEEKLY_RANGE range
        """
        self.data = []

        # Import data
        if self.gs_data_sheet is not None:
            self.data = self.gs_data_sheet.get_values(self.config['sheets']['data']['named_ranges']['data_range'])

            # Identify the first day of the week
            df = self.to_df()
            day = df[self.config['sheets']['data']['columns']['start_time']].min()
            dt = datetime.strptime(day, '%d/%m/%Y')
            self.week_dt = dt - timedelta(days=dt.weekday())
            logging.debug(f'Week: {self.week_dt}')

    def fetch_files(self, weekly: bool = False):
        """
        This function connects to Google Drive and returns arrays of file pointers to PNG and SVG files stored remotly
        """
        self.pngs = []
        self.svgs = []
        if self.gd_client is not None:
            # Search tile files (PNG)
            mimetype = 'image/png'
            query = "'{folder_id}' in parents and mimeType='{mimetype}' and trashed=false".format(
                folder_id=self.config['drive']['png_folder_id'],
                mimetype=mimetype)
            file_list = self.gd_client.ListFile({'q': query}).GetList()
            if len(file_list) > 0:
                for file in file_list:
                    self.pngs.append(file)

            # Search tile files (SVG)
            mimetype = 'image/svg+xml'
            query = "'{folder_id}' in parents and mimeType='{mimetype}' and trashed=false".format(
                folder_id=self.config['drive']['svg_folder_id'],
                mimetype=mimetype)
            file_list = self.gd_client.ListFile({'q': query}).GetList()
            if len(file_list) > 0:
                for file in file_list:
                    self.svgs.append(file)

    def __download_gdrive_file(self, file: GoogleDriveFile, path_file: str, replace: bool = False) -> None:
        """
        This private function takes as input a GoogleDrive file reference, a system fullpath and a boolean to force replace, to
        download the remote file on the local system, overwriting existing file if required.
        """
        # Check if file exists - Skip if found unless replace is forced
        path = Path(path_file).as_posix()
        if not Path(path_file).is_file():
            log.debug("Downloading: '{path}'".format(path=path))
            file.GetContentFile(path, file['mimeType'])
        elif Path(path).is_file() and replace:
            log.debug("Downloading and overwriting: '{path}'".format(path=path))
            file.GetContentFile(path, file['mimeType'])
        else:
            log.info("Skipping: '{path}' - File already exists.".format(path=path))

    def download_png_files(self, path_folder: str = '.', replace: bool = False, weekly: bool = False) -> None:
        """
        This function takes as input a system folder path, a boolean to force replace, and a weekly boolean to download remote
        PNG files to disk, overwriting existing file if required.
        """
        existing_files = []

        # Create directory if missing
        path = Path(path_folder)
        path.mkdir(parents=True, exist_ok=True)

        # Get Weekly files from Sheet
        if weekly:
            existing_files = self.get_files()
        # Only download weekly referenced files.
        # Replace file only if forced.
        if self.pngs is not None:
            for file in self.pngs:
                basename = file['title']
                path = Path(path_folder, basename).as_posix()
                if weekly:
                    filtered_elements = filter(lambda x: x == basename, existing_files)
                    if list(filtered_elements):
                        self.__download_gdrive_file(file, path_file=path, replace=replace)
                else:
                    self.__download_gdrive_file(file, path_file=path, replace=replace)

    def download_svg_files(self, path_folder: str = '.', replace: bool = False, weekly: bool = False) -> None:
        """
        This function takes as input a system folder path, a boolean to force replace, and a weekly boolean to download remote
        SVG files to disk, overwriting existing file if required.
        """
        existing_png = []

        # Create directory if missing
        path = Path(path_folder)
        path.mkdir(parents=True, exist_ok=True)

        # Get Weekly files from Sheet
        if weekly:
            existing_files = self.get_files()
            for basename in existing_files:
                existing_png.append(Path(basename).with_suffix('.svg').name)
        # Only download weekly referenced files.
        # Replace file only if forced.
        if self.svgs is not None:
            for file in self.svgs:
                basename = file['title']
                path = Path(path_folder, basename).as_posix()
                if weekly:
                    filtered_elements = filter(lambda x: x == basename, existing_png)
                    if list(filtered_elements):
                        self.__download_gdrive_file(file, path_file=path, replace=replace)
                else:
                    self.__download_gdrive_file(file, path_file=path, replace=replace)

    def to_df(self) -> DataFrame:
        """
        This function converts the 2D List of data into a DataFrame object
        """
        data = self.data.copy()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        df = df.reset_index()
        return df

    def to_dict(self):
        """
        This function converts the DataFrame into a JSON object
        """
        df = self.to_df()
        d = df.to_dict(orient='records')
        return d

    def download_data(self, path_file, replace: bool = False) -> None:
        """
        This function create a JSON file from imported Event Data
        :param path_file: Target JSON file
        :param replace: True to overwrite existing files
        """
        path = Path(path_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        basename = path.name
        if path.is_file() and not replace:
            log.info("Skipping: '{path}' - File already exists.".format(path=basename))
            return
        elif path.is_file():
            log.debug("Downloading and overwriting: '{path}'".format(path=basename))
        else:
            log.debug("Downloading: '{path}'".format(path=basename))

        # Write JSON data to file
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path_file, 'w', encoding='utf-8') as f:
            d = {
                "week": datetime.strftime(self.week_dt, '%d/%m'),
                "events": self.to_dict()
            }
            json.dump(d, f, ensure_ascii=False, indent=4)

    def download_links(self, path_file, replace: bool = False) -> None:
        """
        This function create a JSON file from imported Event Data
        :param path_file: Target JSON file
        :param replace: True to overwrite existing files
        """
        path = Path(path_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        basename = path.name
        if path.is_file() and not replace:
            log.info("Skipping: '{path}' - File already exists.".format(path=basename))
            return
        elif path.is_file():
            log.debug("Downloading and overwriting: '{path}'".format(path=basename))
        else:
            log.debug("Downloading: '{path}'".format(path=basename))

        # Write JSON data to file
        values = self.__get_column_values('Infos + Lien')
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get links pre/post strings
        pre_text_cell = self.get_config(self.config['sheets']['config']['pre_links_cell'])
        post_text_cell = self.get_config(self.config['sheets']['config']['post_links_cell'])
        pre_text = pre_text_cell.first()
        post_text = post_text_cell.first()

        # Build weekly links text
        links = []
        if pre_text != "":
            links.append(pre_text)
        links.extend(values)
        if post_text != "":
            links.append(post_text)

        # Write weekly links file
        with open(path_file, 'w', encoding='utf-8', newline='') as f:
            f.writelines('\r\n'.join(links))

    def read_config(self):
        """

        :return:
        """


    def __get_column_values(self, name) -> List:
        """
        This function returns a serie of values (column) from the Dataframe. This is used to return all potential values
        of a Sheets column.
        :param name: Column name
        :return:
        """
        lst = []
        if len(self.data) > 0:
            df = self.to_df()
            lst = df[name].tolist()
        return lst

    def get_start_dates(self) -> List:
        """
        This function returns all 'Date Début' values.
        :return: List of strings from 'Date Début' column
        """
        return self.__get_column_values(self.config['sheets']['config']['worksheet_id'])

    def get_start_times(self) -> List:
        """
        This function returns all 'Heure Début' values.
        :return: List of strings from 'Heure Début' column
        """
        return self.__get_column_values('Heure Début')

    def get_end_dates(self) -> List:
        """
        This function returns all 'Date Fin' values.
        :return: List of strings from 'Date Fin' column
        """
        return self.__get_column_values('Date Fin')

    def get_end_times(self) -> List:
        """
        This function returns all 'Heure Fin' values.
        :return: List of strings from 'Heure Fin' column
        """
        return self.__get_column_values('Heure Fin')

    def get_days(self) -> List:
        """
        This function returns all 'Jour' values.
        :return: List of strings from 'Jour' column
        """
        return self.__get_column_values('Jour')

    def get_types(self) -> List:
        """
        This function returns all 'Type' values.
        :return: List of strings from 'Type' column
        """
        return self.__get_column_values('Type')

    def get_end_locs(self) -> List:
        """
        This function returns all 'Lieu / Ecole' values.
        :return: List of strings from 'Lieu / Ecole' column
        """
        return self.__get_column_values('Lieu / Ecole')

    def get_polls(self) -> List:
        """
        This function returns all 'Infos + Lien' values.
        :return: List of strings from 'Infos + Lien' column
        """
        return self.__get_column_values('Infos + Lien')

    def get_short_names(self) -> List:
        """
        This function returns all 'Nom Court' values.
        :return: List of strings from 'Nom Court' column
        """
        return self.__get_column_values('Nom Court')

    def get_names(self) -> List:
        """
        This function returns all 'Nom' values.
        :return: List of strings from 'Nom' column
        """
        return self.__get_column_values('Nom')

    def get_short_urls(self) -> List:
        """
        This function returns all 'Url-Shorten' values.
        :return: List of strings from 'Url-Shorten' column
        """
        return self.__get_column_values('Url-Shorten')

    def get_urls(self) -> List:
        """
        This function returns all 'Url' values.
        :return: List of strings from 'Url' column
        """
        return self.__get_column_values('Url')

    def get_poll_names(self) -> List:
        """
        This function returns all 'Sondage' values.
        :return: List of strings from 'Sondage' column
        """
        return self.__get_column_values('Sondage')

    def get_calendar_names(self) -> List:
        """
        This function returns all 'Calendrier' values.
        :return: List of strings from 'Calendrier' column
        """
        return self.__get_column_values('Calendrier')

    def get_polls(self) -> List:
        """
        This function returns all 'Infos + Lien' values.
        :return: List of strings from 'Infos + Lien' column
        """
        return self.__get_column_values('Infos + Lien')

    def get_files(self) -> List:
        """
        This function returns all 'Image' values.
        :return: List of strings from 'Image' column
        """
        return self.__get_column_values('Image')

    def get_config(self, key):
        """
        This function returns the value of specified ranges in the config worksheet
        :param key: Parameter key to lookup
        :return: Value of the parameter
        """
        value = ""
        try:
            value = self.gs_config_sheet.get(key)
        except:
            value = ""
        return value

    def synchronize_gdrive(self) -> None :
        # Connect to Google Drive and Google Sheet and store both Clients
        log.info("Connecting to Goggle Services")
        self.connect()

        # Pull references to Spreadsheet Data and Drive Files
        log.info("Reading Sheets data")
        self.fetch_data()
        log.info("Reading Drive files")
        self.fetch_files()

        # Manage Content - Download / Create / Upload files
        log.info("Creating JSON data file")
        data_file = Path('.', self.config['app']['data_file'])
        self.download_data(path_file=data_file.absolute().as_posix(), replace=True)

        log.info("Creating URLS file")
        urls_files = Path('.', self.config['app']['export_folder'], datetime.strftime(self.week_dt, '%Y%m%d') + '.txt')
        self.download_links(path_file=urls_files.absolute().as_posix(), replace=True)

        log.info("Downloading PNG files")
        self.download_png_files(path_folder=self.config['app']['png_folder'], replace=True, weekly=True)

        log.info("Downloading SVG files")
        self.download_svg_files(path_folder=self.config['app']['svg_folder'], replace=True, weekly=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    if args.conf is not None:
        logging.basicConfig(level=log.info)

        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        gash = GDriveAgendaHelper(config=config)
        gash.synchronize_gdrive()


if __name__ == '__main__':
    main()
