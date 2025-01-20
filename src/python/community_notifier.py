import argparse
import json
import logging

import yaml
from logging import log

from whatsapp_client import WhatsAppWebClient, ChatsPage

__doc__ = ""

# Define logger
log = logging.getLogger("community_helper")
logging.basicConfig(level=logging.DEBUG)

class CommunityHelper:
    config = None
    whatsapp_client = None
    data = {}

    def __init__(self, config):
        """

        :param config: A JSON structure of configuration elements
        """
        self.config = config
        self.whatsapp_client = WhatsAppWebClient(self.config)

        # Load data file
        with open(self.config['app']['data_file'], 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def process(self) -> None:
        """

        :return:
        """
        # ---------------------------------------------------------------------
        # Step 01: Fetch data to broadcast from previous data sync
        # ---------------------------------------------------------------------
        planning_message = ""
        planning_images = []
        survey_title = ""
        survey_entries = []
        try:
            if self.config['community']['send_planning']:
                # Prepare entries list
                prepare_message = []
                # Append title
                planning_title = self.get_planning_title()
                if planning_title:
                    prepare_message.append(planning_title + '\r\n')
                # Append content
                planning_data = self.get_planning_data()
                prepare_message.extend([item for item in planning_data if item])
                # Append footer
                planning_footer = self.get_planning_footer()
                if planning_footer:
                    prepare_message.append('\r\n' + planning_footer)
                # Join the non-empty strings with CRLF
                planning_message = "\r\n".join(prepare_message)
                logging.debug('Done preparing Planning message and content.')

            if self.config['community']['send_survey']:
                # Prepare text
                survey_title = self.get_survey_title()
                survey_data = self.get_survey_data()
                survey_footer = self.get_survey_footer()
                survey_entries.extend([item for item in survey_data if item])
                if survey_footer:
                    survey_entries.append(survey_footer)

                # Prepare images attachments

                logging.debug('Done preparing Planning message and content.')

        except Exception as e:
            logging.exception('Failed to get data to broadcast.')


        # ---------------------------------------------------------------------
        # Step 02: Fetch images abd attachments to broadcast
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        # Step 03: Broadcast to WhatsApp
        # ---------------------------------------------------------------------
        try:
            # Open WhatsApp
            self.whatsapp_client.startup()
            self.whatsapp_client.open_web_app()

            # Access Chat page
            chat_page = ChatsPage(self.whatsapp_client.browser)

            # Send survey as poll
            for recipient in self.config['community']['survey_recipients']:
                chat_page.create_and_send_new_poll(recipient, title=survey_title, entries=survey_entries, multi=True)

            # Send survey as poll
            for recipient in self.config['community']['planning_recipients']:
                chat_page.create_and_send_new_message(to=recipient, text=planning_message, images=planning_images)

            # Close WhatsApp
            self.whatsapp_client.close_and_quit()

        except Exception as e:
            logging.exception('Failed to fetch configuration !')


    def get_planning_title(self):
        """

        :return: A text used as first line for the Survey communication
        """
        try:
            return self.data['links-title']
        except Exception as e:
            return ""


    def get_planning_data(self):
        """

        :return: A list of values to display as entries for the Survey
        """
        try:
            return [event["Infos"] for event in self.data["events"]]
        except Exception as e:
            return []

    def get_planning_footer(self):
        """

        :return: A text used as last line for the Survey communication
        """
        try:
            return self.data['links-footer']
        except Exception as e:
            return ""

    def get_survey_title(self):
        """

        :return: A text used as first line for the Planning communication
        """
        try:
            return self.data['survey-title']
        except Exception as e:
            return ""

    def get_survey_data(self):
        """

        :return: A list of values to display as entries for the Planning
        """
        try:
            return [event["Sondage"] for event in self.data["events"]]
        except Exception as e:
            return []

    def get_survey_footer(self):
        """
        :return: A text used as last line for the Planning communication
        """
        try:
            return self.data['survey-footer']
        except Exception as e:
            return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--conf', action='append')
    args = parser.parse_args()

    if args.conf is not None:
        logging.basicConfig(level=log.info)

        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        ch = CommunityHelper(config=config)
        ch.process()

if __name__ == '__main__':
    main()