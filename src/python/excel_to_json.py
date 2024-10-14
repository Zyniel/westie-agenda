#!/usr/bin/env python3
from datetime import datetime, timedelta

import pandas as pd
import logging
import yaml
import argparse
from pathlib import Path

__doc__ = "Convert an Excel sheet to JSON."

def get_first_day_of_week(dt):
    return dt - timedelta(days=dt.weekday())

def get_last_day_of_week(day):
    week_start = get_first_day_of_week(day)
    return week_start + timedelta(days=6)

def convert_excel_to_json(excel_file, sheet_name, json_file, date_column):
    try:
        # Read the specific sheet from the Excel file
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')

        # Compute current Week
        day = df[date_column].min()
        dt = datetime.strptime(day, '%m/%d/%Y')
        week_start = get_first_day_of_week(dt)
        week_end = week_start + timedelta(days=6)

        # Convert the DataFrame to JSON
        df.to_json(json_file, orient='records', indent=4, force_ascii=False)
        # Open JSON again
        # TODO: Find better to handle Unicode
        # f = open("job_benefits.json", "a", encoding= 'utf-8')

        # Format JSON adding Week
        # json_events = {
        #     "week" : week_start.strftime('%m/%d'),
        #    "days" :
        # }

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
        convert_excel_to_json(config["excel_file"], config["excel_worksheet"], config["json_file"], config["date_column"])
    else:
        raise Exception("Missing configuration file.")

if __name__ == "__main__":
    main()