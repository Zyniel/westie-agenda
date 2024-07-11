#!/usr/bin/env python3
import pandas as pd
import logging
import yaml
import argparse
from pathlib import Path

__doc__ = "Convert an Excel sheet to JSON."

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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    if args.conf is not None:
        logging.basicConfig(level=logging.INFO)

        # Load configuration file
        with open(args.conf[0], 'r') as file:
            config = yaml.safe_load(file)

        # Download a local copy of the Excel file
        # file_url = "https://api.onedrive.com/v1.0/shares/u!aHR0cHM6Ly8xZHJ2Lm1zL3gvcyFBcmsySUh5dXNNT1doSjBveENZOTllYzE2bVlZS2c_ZT1KRm11/root/content"
        # resp = requests.get(file_url)
        # output = open('WCS-Online.xlsx', 'wb')
        # output.write(resp.content)
        # output.close()

        # Create folder for future file if missing
        p_file = Path(config["json_file"])
        p_file.parent.mkdir(parents=True, exist_ok=True)
        # Convert XLSX to JSON
        convert_excel_to_json(config["excel_file"], config["excel_worksheet"], config["json_file"])
    else:
        raise Exception("Missing configuration file.")

if __name__ == "__main__":
    main()