#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import json
import yaml
import logging

from whatsapp_gmail_login_handler import WhatsAppGmailLoginHandler
from whatsapp_client import WhatsAppWebClient, ChatsPage

__doc__ = "Publish Plannings and Surveys to groups using WhatsApp Web automation."

# Define logger
log = logging.getLogger('com.zyniel.dance.westie-agenda.community-helper')
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.DEBUG)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.DEBUG)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.DEBUG)

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
                log.debug('Done preparing Planning message and content.')

            if self.config['community']['send_survey']:
                # Prepare text
                survey_title = self.get_survey_title()
                survey_data = self.get_survey_data()
                survey_footer = self.get_survey_footer()
                survey_entries.extend([item for item in survey_data if item])
                if survey_footer:
                    survey_entries.append(survey_footer)

                # Prepare images attachments

                log.debug('Done preparing Planning message and content.')

            # Configure Handler
            gmail_handler = WhatsAppGmailLoginHandler(self.config)
            gmail_handler.to = self.config['mail']['sender']
            gmail_handler.subject = self.config['mail']['subject']
            gmail_handler.sender = self.config['mail']['sender']

        except Exception as e:
            log.exception('Failed to get data to broadcast.')
            raise e


        # ---------------------------------------------------------------------
        # Step 02: Fetch images abd attachments to broadcast
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        # Step 03: Broadcast to WhatsApp
        # ---------------------------------------------------------------------
        try:
            # Register email notifier
            self.whatsapp_client.notifiers.append(gmail_handler)
            # Open WhatsApp
            self.whatsapp_client.startup()
            # self.whatsapp_client.open_web_app()
            self.whatsapp_client.login()

            # Access Chat page
            chat_page = ChatsPage(self.whatsapp_client.browser)
        except Exception as e:
            log.exception('Failed to initialise WhatsApp Web Client !!')
            raise e

        try:
            # Send Information
            # TODO: Fin a way to combine recipients list and iterate by recipient
            for recipient in self.config['community']['planning_recipients']:
                log.info(f"Sending events Information to: {recipient}")
                try:
                    chat_page.create_and_send_new_message(to=recipient, text=planning_message, images=planning_images)
                    log.warning("Successfully sent Information !")
                except Exception as e:
                    log.warning("Failed to send events Information!")

            # Send Polls
            for recipient in self.config['community']['survey_recipients']:
                try:
                    log.info("Sending events Poll to: {recipient}")
                    chat_page.create_and_send_new_poll(recipient, title=survey_title, entries=survey_entries, multi=True)
                    log.warning("Successfully sent events Poll !")
                except Exception as e:
                    log.warning("Failed to send events Poll !")

            # Close WhatsApp
            self.whatsapp_client.close_and_quit()

        except Exception as e:
            log.exception('Failed to send all data to recipients !!')
            raise e


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
        logging.basicConfig(level=logging.INFO)

        # Load configuration file
        with open(args.conf[0], 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        ch = CommunityHelper(config=config)
        ch.process()

if __name__ == '__main__':
    main()