#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
from datetime import datetime, timedelta

import gspread
import logging
import json
import pandas as pd
import yaml
import argparse

from typing import List, Tuple
from pathlib import Path

from pandas import Series, DataFrame
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.files import GoogleDriveFile
from imagekitio import ImageKit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from pil_mosaic_helper import PILMosaicHelper
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool

__doc__ = "Synchronize events between the remote Google Drive/Sheets and the Repo to build the GitHub Page"

# A single auth scope is used for the zero-touch enrollment customer API.
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

# Define logger
__logger_builder__ = 'com.zyniel.dance.westie-agenda.site-builder'
log = logging.getLogger(__logger_builder__)

def to_dict(dataframe: DataFrame | Series) -> dict:
    """
    Returns a 2D Dictionary based on the DataFrame object.

    :param dataframe: The DataFrame to be converted to a Dictionary
    :return: Dictionnary object of data from the DataFrame
    """
    if isinstance(dataframe, DataFrame):
        d = dataframe.to_dict(orient='records')
    else:
        d = dataframe.to_dict()
    return d


def to_df(lst) -> pd.DataFrame:
    """
    This function converts the 2D List of data into a DataFrame object.

    :param lst: The 2D list of data to be converted into a DataFrame.
    :return: DataFrame object created from the 2D list.
    """
    data = lst.copy()
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    df = df.reset_index()
    return df


class GDriveAgendaHelper:

    def __init__(self, config):
        self.pngs_hd = None
        self.week_dt = None
        self.pngs = []
        self.svgs = []
        self.data = []
        self.params = []
        self.df = None
        self.df_params = None
        self.scopes = SCOPES
        self.gs_client = None
        self.gs_spreadsheet = None
        self.gs_data_sheet = None
        self.gs_config_sheet = None
        self.gs_whatsapp_sheet = None
        self.gd_client = None
        self.ik_client = None
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
        gs_whatsapp_sheet = gs_spreadsheet.worksheet(self.config['sheets']['whatsapp']['worksheet_id'])
        self.gs_whatsapp_sheet = gs_whatsapp_sheet

        # Connect to Google DRIVE API using Service Account using  Bearer Token
        gauth = GoogleAuth()
        gauth.auth_method = 'service'
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            filename=self.config['drive']['service_account_key'],
            scopes=SCOPES)
        self.gd_client = GoogleDrive(gauth)

        # Connect to ImageKit
        imagekit = ImageKit(
            private_key=os.environ['IK_SERVICE_ACCOUNT'],
            public_key=self.config['imagekit']['public_key'],
            url_endpoint=self.config['imagekit']['url_endpoint']
        )
        self.ik_client = imagekit

    def fetch_properties(self):
        """
        This function connects to Google Sheets and returns values inside the CONFIG Sheet
        """
        self.params = []

        # Import properties
        if self.params is not None:
            self.params = self.gs_config_sheet.get_all_values()
            self.df_params = to_df(self.params)

    def fetch_data(self):
        """
        This function connects to Google Sheets and returns values inside the SEMAINE Sheet
        """
        self.data = []

        # Import data
        if self.gs_data_sheet is not None:
            self.data = self.gs_data_sheet.get_all_values()

            # Identify the first day of the week
            self.df = to_df(self.data)
            day = self.df[self.config['sheets']['data']['columns']['start_time']].min()
            dt = datetime.strptime(day, '%d/%m/%Y')
            self.week_dt = dt - timedelta(days=dt.weekday())
            log.debug(f'Week: {self.week_dt}')

    def fetch_files(self, weekly: bool = False):
        """
        This function connects to Google Drive and returns arrays of file pointers to PNG and SVG files stored remotly
        """
        self.pngs = []
        self.pngs_hd = []
        self.svgs = []
        if self.gd_client is not None:
            # Search tile files (PNG)
            mimetype = 'image/png'
            query = "'{folder_id}' in parents and mimeType='{mimetype}' and trashed=false".format(
                folder_id=self.config['drive']['folder_id_png'],
                mimetype=mimetype)
            file_list = self.gd_client.ListFile({'q': query}).GetList()
            if len(file_list) > 0:
                for file in file_list:

                    if file['title'].endswith(self.config['app']['image_hd_suffix'] + '.png'):
                        self.pngs_hd.append(file)
                    else:
                        self.pngs.append(file)

            # Search tile files (SVG)
            mimetype = 'image/svg+xml'
            query = "'{folder_id}' in parents and mimeType='{mimetype}' and trashed=false".format(
                folder_id=self.config['drive']['folder_id_svg'],
                mimetype=mimetype)
            file_list = self.gd_client.ListFile({'q': query}).GetList()
            if len(file_list) > 0:
                for file in file_list:
                    self.svgs.append(file)

    def __download_gdrive_file_parallel(self, args):
        """
        Single parameter function for parallel processing of downloads

        :param args: Tuple containing a GoogleDriveFile, the file path as a string and a boolean switch to handle file overwrite
        :return: The filepath and total download duration
        """
        cpus = cpu_count()
        results = ThreadPool(cpus - 1).imap_unordered(self.__download_gdrive_file_thread, args)
        log.debug('----- Download Statistics ------------------')
        for result in results:
            log.debug(f'File:{result[0]}, time (s): {result[1]}')
        log.debug('--------------------------------------------')

    def __download_gdrive_file_thread(self, args):
        """
        Single parameter wrapper function for parallel processing of downloads

        :param args: Tuple containing a GoogleDriveFile, the file path as a string and a boolean switch to handle file overwrite
        :return: The filepath and total download duration
        """
        # To track duration
        t0 = time.time()
        # Start download
        file = args[0]
        path_file = args[1]
        replace = args[2]
        self.__download_gdrive_file(file, path_file, replace)

        return path_file, time.time() - t0

    def __download_gdrive_file(self, file: GoogleDriveFile, path_file: str, replace: bool = False) -> None:
        """
        This private function downloads a GoogleDrive file to the local system.

        :param file: GoogleDrive file reference to be downloaded.
        :param path_file: The full path where the file will be saved locally.
        :param replace: If True, existing files will be overwritten. Default is False.
        :return: None
        """

        # Check if file exists - Skip if found unless replace is forced
        path = Path(path_file).as_posix()
        if not Path(path_file).is_file():
            log.info("Downloading: '{path}'".format(path=path))
            file.GetContentFile(path, file['mimeType'])
        elif Path(path).is_file() and replace:
            log.info("Downloading and overwriting: '{path}'".format(path=path))
            file.GetContentFile(path, file['mimeType'])
        else:
            log.info("Skipping: '{path}' - File already exists.".format(path=path))

    def __upload_file_to_cdn_parallel(self, args):
        """
        Single parameter function for parallel processing of downloads

        :param args: Tuple containing a GoogleDriveFile, the file path as a string and a boolean switch to handle file overwrite
        :return: The filepath and total download duration
        """
        cpus = cpu_count()
        results = ThreadPool(cpus - 1).imap_unordered(self.__upload_file_to_cdn_thread, args)
        log.debug('----- Upload Statistics --------------------')
        for result in results:
            log.debug(f'File:{result[0]}, time (s): {result[1]}')
        log.debug('--------------------------------------------')

    def __upload_file_to_cdn_thread(self, args):
        """
        Single parameter wrapper function for parallel processing of downloads

        :param args: Tuple containing a GoogleDriveFile, the file path as a string and a boolean switch to handle file overwrite
        :return: The filepath and total download duration
        """
        # To track duration
        t0 = time.time()
        # Start download
        path_file = args[0]
        replace = args[1]
        self.__upload_file_to_cdn(path_file, replace)
        return path_file, time.time() - t0

    def __upload_file_to_cdn(self, path_file: str = '.', replace: bool = False) -> None:
        """
        This private function takes as input a local file path, and a boolean to force replace, and uploads the file to
        the remote CDN through API calls.

        :param path_file: String path iof the file to upload
        :param replace: Boolean switch to force replacement
        """
        # Check if file exists - Skip if found unless replace is forced
        path = Path(path_file)
        basename = Path(path_file).name

        if not path.is_file() or (path.is_file() and replace):
            if replace:
                log.debug("Uploading and replacing: '{basename}'".format(basename=basename))
            else:
                log.debug("Uploading: '{basename}'".format(basename=basename))

            with path.open('rb') as file:
                upload = self.ik_client.upload_file(
                    file=file,
                    file_name=basename,
                    options=UploadFileRequestOptions(
                        use_unique_file_name=False,
                        folder=self.config['imagekit']['folder_png'],
                        overwrite_file=True,
                    )
                )
                # TODO: Add upload validation
                log.info("Uploaded to CDN: {basename} (id: {id})".format(basename=basename, id=upload.file_id))
        else:
            log.info("Skipping: '{path}' - File already exists.".format(path=path))

    def __is_hd_image(self, basename: str) -> bool:
        return self.config['app']['image_hd_suffix'] in basename

    def download_png_files(self, path_folder: str = '.', replace: bool = False, weekly: bool = False) -> None:
        """
        Download PNG files to disk.

        :param path_folder: The system folder path where PNG files will be downloaded. Default is the current directory.
        :param replace: If True, existing files will be overwritten. Default is False.
        :param weekly: If True, only download PNG files referenced weekly. Default is False.
        :return: None
        """
        log.info("Starting download of PNG files.")

        path = Path(path_folder)
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"Directory created: {path_folder}")

        images = self.get_files() if weekly else []
        log.info(f"Weekly mode: {weekly}. Number of existing files: {len(images)}")

        if self.pngs:
            paths = []
            files = []
            bools = []
            inputs = None

            # Download standard pictures
            for file in self.pngs:
                basename = file['title']
                if not weekly or basename in images:
                    file_path = Path(path_folder, basename).as_posix()
                    files.append(file)
                    paths.append(file_path)
                    bools.append(replace)
                    inputs = zip(files, paths, bools)
            self.__download_gdrive_file_parallel(inputs)

    def download_hd_png_files(self, path_folder: str = '.', replace: bool = False, weekly: bool = False) -> None:
        """
        Download PNG files to disk.

        :param path_folder: The system folder path where PNG files will be downloaded. Default is the current directory.
        :param replace: If True, existing files will be overwritten. Default is False.
        :param weekly: If True, only download PNG files referenced weekly. Default is False.
        :return: None
        """
        log.info("Starting download of PNG files.")

        path = Path(path_folder)
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"Directory created: {path_folder}")

        images = self.get_files() if weekly else []
        images = [Path(basename).with_name(Path(basename).stem + self.config['app']['image_hd_suffix'] + Path(basename).suffix).name for basename in images]
        log.info(f"Weekly mode: {weekly}. Number of existing files: {len(images)}")

        if self.pngs_hd:
            paths = []
            files = []
            bools = []
            inputs = None

            # Download standard pictures
            for file in self.pngs_hd:
                basename = str(file['title'])
                if not weekly or basename in images:
                    file_path = Path(path_folder, basename).as_posix()
                    files.append(file)
                    paths.append(file_path)
                    bools.append(replace)
                    inputs = zip(files, paths, bools)

            # TODO : Reconsider use
            # else:
            #     log.debug(f"Skipped file: {basename}")
            if not inputs is None:
                self.__download_gdrive_file_parallel(inputs)

    def download_svg_files(self, path_folder: str = '.', replace: bool = False, weekly: bool = False) -> None:
        """
        Download SVG files to disk.

        :param path_folder: The system folder path where SVG files will be downloaded. Default is the current directory.
        :param replace: If True, existing files will be overwritten. Default is False.
        :param weekly: If True, only download SVG files referenced weekly. Default is False.
        :return: None.
        """
        path = Path(path_folder)
        path.mkdir(parents=True, exist_ok=True)
        log.info(f"Directory created: {path_folder}")

        images = self.get_files() if weekly else []
        images = [Path(basename).with_suffix('.svg').name for basename in images]
        log.info(f"Weekly mode: {weekly}. Number of existing SVG files: {len(images)}")

        if self.svgs:
            paths = []
            files = []
            bools = []
            inputs = None
            for file in self.svgs:
                basename = file['title']
                if not weekly or basename in images:
                    file_path = Path(path_folder, basename).as_posix()
                    files.append(file)
                    paths.append(file_path)
                    bools.append(replace)
                    inputs = zip(files, paths, bools)
            # TODO : Reconsider use
            # else:
            #     log.debug(f"Skipped file: {basename}")

            if not inputs is None:
                self.__download_gdrive_file_parallel(inputs)

    def upload_png_files_to_cdn(self, path_folder: str = '.', replace: bool = False, weekly: bool = False):
        """
        This function uploads PNG tiles to CDN.

        :param path_folder: Source folder for content.
        :param replace: Switch to overwrite any existing remote reference.
        :param weekly: Switch to only consider weekly files instead of whole scope.
        :return: None
        """
        log.info("Starting upload of PNG files to CDN.")

        # Get Weekly files from Sheet
        images = self.get_files() if weekly else []
        log.info(f"Weekly mode: {weekly}. Number of existing files: {len(images)}")

        # Directory containing images
        directory = Path(path_folder)

        # Loop through files and upload
        files = []
        bools = []
        inputs = None
        for path_image in directory.glob('*.png'):
            basename = path_image.name
            if not self.__is_hd_image(basename):
                absolute_path = path_image.absolute().as_posix()
                if not weekly or basename in images:
                    files.append(absolute_path)
                    bools.append(replace)
                    inputs = zip(files, bools)
                # TODO : Reconsider use
                # else:
                #     log.debug(f"Skipped file: {basename}")

        if not inputs is None:
            self.__upload_file_to_cdn_parallel(inputs)

    def upload_hd_png_files_to_cdn(self, path_folder: str = '.', replace: bool = False, weekly: bool = False):
        """
        This function uploads PNG tiles to CDN.

        :param path_folder: Source folder for content.
        :param replace: Switch to overwrite any existing remote reference.
        :param weekly: Switch to only consider weekly files instead of whole scope.
        :return: None
        """
        log.info("Starting upload of PNG files to CDN.")

        # Get Weekly files from Sheet
        images = self.get_files() if weekly else []
        images = [Path(basename).with_name(Path(basename).stem + self.config['app']['image_hd_suffix'] + Path(basename).suffix).name for basename in images]
        log.info(f"Weekly mode: {weekly}. Number of existing files: {len(images)}")

        # Directory containing images
        directory = Path(path_folder)

        # Loop through files and upload
        files = []
        bools = []
        inputs = None
        for path_image in directory.glob('*' + self.config['app']['image_hd_suffix'] + '.png'):
            basename = path_image.name
            absolute_path = path_image.absolute().as_posix()
            if not weekly or basename in images:
                files.append(absolute_path)
                bools.append(replace)
                inputs = zip(files, bools)
            # TODO : Reconsider use
            # else:
            #     log.debug(f"Skipped file: {basename}")

        if not inputs is None:
            self.__upload_file_to_cdn_parallel(inputs)

    def process_images(self, replace: bool = False, weekly: bool = False):

        # Get Weekly files from Sheet
        planning_names = self.get_files() if weekly else []

        vector_images = []
        raster_sd_images = []
        raster_hd_images = []
        vector_files = []
        raster_sd_files = []
        raster_hd_files = []
        bools = []

        # Weekly: Process only images from the weekly planning
        if weekly:
            planning_stems = [ Path(name).stem for name in planning_names ]

            for stem in planning_stems:
                vector_basename = stem + '.svg'
                raster_sd_basename = stem + '.png'
                raster_hd_basename = stem + self.config['app']['image_hd_suffix'] + '.png'
                vector_path = Path(self.config['app']['svg_folder'], vector_basename).as_posix()
                raster_sd_path = Path(self.config['app']['png_folder'], raster_sd_basename).as_posix()
                raster_hd_path = Path(self.config['app']['png_folder'], raster_hd_basename).as_posix()

                # Check if vector file exists
                vector_exists = False
                vector_file = None
                for file in self.svgs:
                    vector_exists = (file['title'] == vector_basename)
                    if vector_exists:
                        vector_file = file
                        break

                # Check if low definition file exists
                raster_sd_exists = False
                raster_sd_file = None
                for file in self.pngs:
                    raster_sd_exists = (file['title'] == raster_sd_basename)
                    if raster_sd_exists:
                        raster_sd_file = file
                        break

                # Check if high definition file exists
                raster_hd_exists = False
                raster_hd_file = None
                for file in self.pngs_hd:
                    raster_hd_exists = (file['title'] == raster_hd_basename)
                    if raster_hd_exists:
                        raster_hd_file = file
                        break

                if vector_exists and raster_sd_exists and raster_hd_exists:
                    vector_images.append(vector_path)
                    vector_files.append(vector_file)
                    raster_sd_images.append(raster_sd_path)
                    raster_sd_files.append(raster_sd_file)
                    raster_hd_images.append(raster_hd_path)
                    raster_hd_files.append(raster_hd_file)
                    bools.append(replace)
                    log.debug(f'Image "{stem}" is fully uploaded. SVG:{vector_exists} - SD:{raster_sd_exists} - HD:{raster_hd_exists}')
                else:
                    log.warning(f'Image "{stem}" is not fully uploaded. SVG:{vector_exists} - SD:{raster_sd_exists} - HD:{raster_hd_exists}')

        # Full: Process all available images from the repo
        else:
            images = dict()

            # Build a dictionary to hold, per file unified key, a reference to the relevant raster/raster_hd and vector file.
            # A unified key is built to keep the stem and remove any suffix.
            # Vector   : EVT-MyEventIsGreat-2025-Tile.svg (Remove extension)
            # Rast. SD : EVT-MyEventIsGreat-2025-Tile.png (Remove extension)
            # Rast. HD : EVT-MyEventIsGreat-2025-Tile-1200px.png (Remove suffix + extension)
            # Unified  : EVT-MyEventIsGreat-2025-Tile

            # Add all vector files to a dictionary.
            for file in self.svgs:
                filename_base = Path(file['title']).stem
                if not filename_base in images:
                    images[filename_base] = {
                        'vector': file,
                        # 'raster' : None,
                        # 'raster_hd': None
                    }

            # Complete dictionary with raster files.
            for file in self.pngs:
                filename_base = Path(file['title']).stem
                if filename_base in images:
                    images[filename_base]['raster'] = file
                else:
                    images[filename_base] = {
                        # 'vector': None,
                        'raster' : file,
                        # 'raster_hd': None
                    }

            # Complete dictionary with raster hd files.
            for file in self.pngs_hd:
                filename_base = Path(file['title']).stem.removesuffix(self.config['app']['image_hd_suffix'])
                if filename_base in images:
                    images[filename_base]['raster_hd'] = file
                else:
                    images[filename_base] = {
                        # 'vector': None,
                        # 'raster' : None,
                        'raster_hd': file
                    }

            # Sort dictionary
            images = dict(sorted(images.items()))
            for stem, files in images.items():
                vector_exists = ('vector' in files)
                raster_sd_exists = ('raster' in files)
                raster_hd_exists = ('raster_hd' in files)
                if len(files.values()) == 3:
                    vector_basename = stem + '.svg'
                    raster_sd_basename = stem + '.png'
                    raster_hd_basename = stem + self.config['app']['image_hd_suffix'] + '.png'
                    vector_path = Path(self.config['app']['svg_folder'], vector_basename).as_posix()
                    raster_sd_path = Path(self.config['app']['png_folder'], raster_sd_basename).as_posix()
                    raster_hd_path = Path(self.config['app']['png_folder'], raster_hd_basename).as_posix()
                    vector_images.append(vector_path)
                    vector_files.append(files['vector'])
                    raster_sd_images.append(raster_sd_path)
                    raster_sd_files.append(files['raster'])
                    raster_hd_images.append(raster_hd_path)
                    raster_hd_files.append(files['raster_hd'])
                    bools.append(replace)
                    log.debug(f'Image "{stem}" is fully uploaded. SVG:{vector_exists} - SD:{raster_sd_exists} - HD:{raster_hd_exists}')
                else:
                    log.warning(f'Image "{stem}" is not fully uploaded. SVG:{vector_exists} - SD:{raster_sd_exists} - HD:{raster_hd_exists}')


        # Proceed to download - download if content to proceed
        # TODO : Redesign the "all images are necessary" paradigm.
        # TODO : Download all at once ? Readability vs Speed
        if vector_images or raster_sd_images or raster_hd_images:
            vector_input = zip(vector_files, vector_images, bools)
            self.__download_gdrive_file_parallel(vector_input)

            raster_sd_input = zip(raster_sd_files, raster_sd_images, bools)
            self.__download_gdrive_file_parallel(raster_sd_input)

            raster_hd_input = zip(raster_hd_files, raster_hd_images, bools)
            self.__download_gdrive_file_parallel(raster_hd_input)

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

        # Build JSON combined data and write it to file
        with open(path_file, 'w', encoding='utf-8') as f:
            d = self.data_as_dict()
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

        # Get all values from the Google Sheets
        values = self.gs_whatsapp_sheet.get_all_values()

        # Convert values to a DataFrame
        df = to_df(values)

        # Check if the DataFrame has the expected column
        links_column = self.config['sheets']['whatsapp']['columns']['infos']
        if links_column not in df.columns:
            raise ValueError(f"Column '{links_column}' not found in DataFrame")

        # Access the first value of the links column
        links = df[links_column].iloc[0]

        # Check if the value is not empty or None
        if pd.isnull(links) or links == '':
            raise ValueError(f"The first value in column '{links_column}' is empty or None")

        with open(path_file, 'w', encoding='utf-8', newline='') as f:
            f.writelines(links)

    def data_as_dict(self) -> dict:
        return {
            "week": datetime.strftime(self.week_dt, '%d/%m'),
            "week_full": [datetime.strftime(self.week_dt, '%Y%m%d')],
            "events": to_dict(self.df),
            "survey-title": self.get_config('pre-survey-text').strip(),
            "survey-footer": self.get_config('post-survey-text').strip(),
            "links-title": self.get_config('pre-links-text').strip(),
            "links-footer": self.get_config('post-links-text').strip()
        }

    def __get_column_values(self, name) -> List:
        """
        This function returns a serie of values (column) from the Dataframe. This is used to return all potential values
        of a Sheets column.
        :param name: Column name
        :return:
        """
        lst = []
        if len(self.data) > 0:
            lst = self.df[name].tolist()
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
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_end_dates(self) -> List:
        """
        This function returns all 'Date Fin' values.
        :return: List of strings from 'Date Fin' column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_end_times(self) -> List:
        """
        This function returns all 'Heure Fin' values.
        :return: List of strings from 'Heure Fin' column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_days(self) -> List:
        """
        This function returns all 'Jour' values.
        :return: List of strings from 'Jour' column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_types(self) -> List:
        """
        This function returns all 'Type' values.
        :return: List of strings from 'Type' column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_owners(self) -> List:
        """
        This function returns all 'Organisateur' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['owner'])

    def get_places(self) -> List:
        """
        This function returns all 'Infos + Lien' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['place'])

    def get_locations(self) -> List:
        """
        This function returns all 'Lieu / Ecole' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['location'])

    def get_cities(self) -> List:
        """
        This function returns all 'Lieu / Ecole' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['city'])

    def get_addresses(self) -> List:
        """
        This function returns all 'Lieu / Ecole' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['address'])

    def get_short_names(self) -> List:
        """
        This function returns all 'Nom Court' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['event_shortname'])

    def get_names(self) -> List:
        """
        This function returns all 'Nom' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['event_name'])

    def get_short_urls(self) -> List:
        """
        This function returns all 'Lien Court' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['short_url'])

    def get_urls(self) -> List:
        """
        This function returns all 'Url' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['url'])

    def get_poll_names(self) -> List:
        """
        This function returns all 'Sondage' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['survey_text'])

    def get_calendar_names(self) -> List:
        """
        This function returns all 'Planning' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['planning_text'])

    def get_poll_infos(self) -> List:
        """
        This function returns all 'Infos' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['infos_text'])

    def get_files(self) -> List:
        """
        This function returns all 'Image' values.
        :return: List of strings from column
        """
        return self.__get_column_values(self.config['sheets']['data']['columns']['image'])

    def get_config(self, key):
        """
        This function returns the value of specified ranges in the config worksheet
        :param key: Parameter key to lookup
        :return: Value of the parameter
        """
        value = ""
        param_header = self.config['sheets']['config']['columns']['parameter']
        value_header = self.config['sheets']['config']['columns']['value']
        try:
            # Ensure the DataFrame contains the expected columns
            if param_header not in self.df_params.columns or value_header not in self.df_params.columns:
                raise ValueError("DataFrame must contain param_header and value_header columns")

            # Access the value of the specified property
            value = self.df_params[self.df_params[param_header] == key][value_header]

            # Check if the property exists and return its value
            if not value.empty:
                return value.iloc[0]
            else:
                raise KeyError(f"Property '{key}' not found in DataFrame")
        except Exception as e:
            value = ""
        return value

    def process(self, weekly: bool = True) -> None:
        # Connect to Google Drive and Google Sheet and store both Clients
        log.info("Connecting to Goggle Services")
        self.connect()

        # Pull references to Spreadsheet Data and Drive Files
        log.info("Reading Sheets data")
        self.fetch_data()
        log.info("Reading Config data")
        self.fetch_properties()
        log.info("Reading Drive files")
        self.fetch_files()

        # Manage Content - Download / Create / Upload files
        log.info("Creating JSON data file")
        data_file = Path('.', self.config['app']['data_file'])
        self.download_data(path_file=data_file.absolute().as_posix(), replace=True)
        data_file = Path('.', self.config['app']['export_folder'], f'{self.week_dt.strftime('%Y%m%d')}.json')
        self.download_data(path_file=data_file.absolute().as_posix(), replace=True)

        log.info("Creating URLS file")
        urls_files = Path('.', self.config['app']['export_folder'], datetime.strftime(self.week_dt, '%Y%m%d') + '.txt')
        self.download_links(path_file=urls_files.absolute().as_posix(), replace=True)

        # log.info("Downloading PNG files")
        # self.download_png_files(path_folder=self.config['app']['png_folder'], replace=True, weekly=weekly)

        # log.info("Downloading HD PNG files")
        # self.download_hd_png_files(path_folder=self.config['app']['png_folder'], replace=True, weekly=weekly)

        # log.info("Downloading SVG files")
        # self.download_svg_files(path_folder=self.config['app']['svg_folder'], replace=True, weekly=weekly)

        self.process_images(replace=True, weekly=weekly)

        log.info("Uploading PNG files to CDN")
        self.upload_png_files_to_cdn(path_folder=self.config['app']['png_folder'], replace=True, weekly=weekly)

        log.info("Uploading HD PNG files to CDN")
        self.upload_hd_png_files_to_cdn(path_folder=self.config['app']['png_folder'], replace=True, weekly=weekly)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    PROJECT_ROOT = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.pardir)
    )
    sys.path.append(PROJECT_ROOT)

    if args.conf is not None:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger('com.zyniel.dance').setLevel(logging.INFO)
        logging.getLogger("google.auth").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)


        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        # Pull events from Google Sheets and updated files from Google Drive
        # to build the weekly plannings and surveys with fresh data
        gash = GDriveAgendaHelper(config=config)
        gash.process(weekly=True)

        # Create event mosaic as PNG and JPG files
        json_data = gash.data_as_dict()
        mh = PILMosaicHelper(config=config, data=json_data)
        mh.create()
        mh.save_as_jpg(str(Path(config['app']['export_folder'], f'{json_data['week_full'][0]}.jpg')))
        mh.save_as_png(str(Path(config['app']['export_folder'], f'{json_data['week_full'][0]}.png')))


if __name__ == '__main__':
    main()
