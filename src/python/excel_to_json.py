#!/usr/bin/env python3
import pandas as pd
import json
import logging
import argparse
import requests
import yaml


def convert_excel_to_json(excel_file, sheet_name, json_file):
    try:
        # Read the specific sheet from the Excel file
        df = pd.read_excel(excel_file, sheet_name=sheet_name)

        # Convert the DataFrame to JSON
        df.to_json(json_file, orient='records', lines=True)

        logging.info(f"Successfully converted {sheet_name} from {excel_file} to {json_file}")
    except Exception as e:
        logging.error(f"Error converting {sheet_name} from {excel_file} to {json_file}: {e}")
        exit(1)

def main():
    logging.basicConfig(level=logging.INFO)

    # Download a local copy of the Excel file
    # file_url = "https://api.onedrive.com/v1.0/shares/u!aHR0cHM6Ly8xZHJ2Lm1zL3gvcyFBcmsySUh5dXNNT1doSjBveENZOTllYzE2bVlZS2c_ZT1KRm11/root/content"
    # resp = requests.get(file_url)
    # output = open('WCS-Online.xlsx', 'wb')
    # output.write(resp.content)
    # output.close()

    # Load configuration file
    with open('config.yml', 'r') as file:
        config = yaml.safe_load(file)

    # Convert XLSX to JSON
    convert_excel_to_json(config["excel_file"], config["excel_worksheet"], config["json_file"])

    # convert_excel_to_json(args.excel_file, args.sheet_name, args.json_file)

if __name__ == "__main__":
    main()