import logging
import sys
from datetime import time
from enum import Enum
from pathlib import Path
import time
from typing import Tuple

import undetected_chromedriver as uc
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# display = Display(visible=True, size=(1200, 1200))
# display.start()

# class syntax
class AppPage(Enum):
    STARTUP = 1
    LOGIN = 2
    LOADING = 3
    MAIN = 4
    UNKNOWN = 99


class WhatsAppWebClient(object):
    browser = None
    config = None
    wait = None
    by_initial_startup = (
        By.ID,
        'wa_web_initial_startup'
    )
    by_auth_page = (
        By.XPATH,
        '//div[contains(@class,"_akau") and @data-ref]'
    )
    by_loading_page = (
        By.XPATH,
        '//progress[@max="100"]'
    )
    by_main_page = (
        By.XPATH,
        '//div[@data-js-navbar="true"]'
    )
    ChatMenu = None

    def __init__(self, config):
        self.wait = None
        self.config = config

        self._current_panel = None

        # set options as you wish
        chrome_options = uc.ChromeOptions()

        # Add your options as needed
        options = [
            # Define window size here
            "--window-size=1200,1200",
            "--ignore-certificate-errors"
            "--disable-infobars"
            "start-maximized"
            "--disable-extensions"
            # "--headless",
            # "--disable-gpu",
            # "--window-size=1920,1200",
            # "--ignore-certificate-errors",
            # "--disable-extensions",
            # "--no-sandbox",
            # "--disable-dev-shm-usage",
            # '--remote-debugging-port=9222'
        ]

        for option in options:
            chrome_options.add_argument(option)

        if self.config['chrome']['user_dir_folder']:
            chrome_options.add_argument("--user-data-dir=" + self.config['chrome']['user_dir_folder'])

        # setup Edge Driver
        self.browser = uc.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.browser, 20)
        self.ChatMenu = ChatsPage(self.browser)

    def check_current_page(self) -> AppPage:
        conditions = {
            AppPage.STARTUP: self.by_initial_startup,
            AppPage.LOGIN: self.by_auth_page,
            AppPage.LOADING: self.by_loading_page,
            AppPage.MAIN: self.by_main_page
        }

        key = AppPage.UNKNOWN
        for condition in conditions:
            try:
                element = self.browser.find_element(*conditions[condition])
                key = condition
            except NoSuchElementException as e:
                pass

        return key

    def send_message(self, to, message=""):
        # many a times class name or other HTML properties changes so keep a track of current class name for input box by using inspect elements
        input_path = '//*[@id="main"]/footer//p[@class="selectable-text copyable-text"]'
        box = self.wait.until(EC.presence_of_element_located((By.XPATH, input_path)))
        # wait for security
        time.sleep(1)
        # send your message followed by an Enter
        box.send_keys(message + Keys.ENTER)
        # wait for security
        time.sleep(2)

    def get_back(self):
        """
        Simulate a back action on browser.
        """
        self.browser.back()

    def open_web_app(self):
        self.browser.get("https://web.whatsapp.com/")

    def login(self):
        try:

            self.browser.get("https://web.whatsapp.com/")
            self.browser.maximize_window()
            self.wait = WebDriverWait(driver=self.browser, timeout=200)

            # wait 5s until leanding page displays
            try:
                landing = WebDriverWait(driver=self.browser, timeout=20).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@class="landing-main"]'))
                )
                if landing:
                    print("Scan QR Code, And then Enter")
                    input()
                    print("Logged In")
            except TimeoutException as e:
                print("No need to authenticate !")

        except Exception as e:
            logging.info("There was some error while logging in.")
            logging.info(sys.exc_info()[0])
            exit()

    def search(self, string):
        # identify contact / group
        name_argument = f"//span[contains(@title,'{string}')]"
        title = self.wait.until(EC.presence_of_element_located((By.XPATH, name_argument)))
        title.click()

    def display_user_agent(self):
        # Fetch the current user agent to verify
        current_user_agent = self.browser.execute_script("return navigator.userAgent;")
        print("Current User Agent:", current_user_agent)

    def close_and_quit(self):
        """
        Close current browser page and quit browser instance
        """
        self.browser.close()
        self.browser.quit()


class WhatsAppPage(object):
    """
    Abstract class to represent a genuine WhatsApp Web page.
    Exposes common browsing capabilities through the sidebar.
    """
    driver = None
    key_element = (
        By.CSS_SELECTOR,
        '#app > div > div.x78zum5.xdt5ytf.x5yr21d > div > header'
    )

    # Sidebar General Buttons
    # Used XPATH Selector to hand the :has() not supported in Selenium
    # NOTE: Update fields if necessary. They are dynamic and change in time.
    by_chats_button = (
        By.XPATH,
        '//header//button[@role="button" and .//span[starts-with(@data-icon,"chats")]]'
    )
    by_status_button = (
        By.XPATH,
        '//header//button[@role="button" and .//span[starts-with(@data-icon,"status")]]'
    )
    by_channels_button = (
        By.XPATH,
        '//header//button[@role="button" and .//span[starts-with(@data-icon,"newsletter")]]'
    )
    by_communities_button = (
        By.XPATH,
        '//header//button[@role="button" and .//span[starts-with(@data-icon,"community")]]'
    )
    by_settings_button = (
        By.XPATH,
        '//header//button[@role="button" and .//span[starts-with(@data-icon,"settings")]]'
    )
    # Sidebar Profile Icon
    # TODO: Handle a better way to avoid selecting with translatable field
    by_profile_button = (
        By.CSS_SELECTOR,
        'button[role="button"][class="x78zum5 x6s0dn4 x1afcbsf x1heor9g x1y1aw1k x1sxyh0 xwib8y2 xurb0ha"][aria-label="Profil"]'
    )

    def __init__(self, driver: WebDriver):
        if driver is None:
            raise TypeError
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)
        self.shortwait = WebDriverWait(driver, 2)

    def wait_until_loaded(self):
        sidebar = self.wait.until(EC.presence_of_element_located(self.key_element))
        logging.debug('Main Page loaded !')

    def click_communities_sidebar_button(self) -> None:
        """
        Clicks the "Communities" sidebar button to reach Communities dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_communities_button))
        element.click()
        logging.debug('Clicked "Communities" in Sidebar')

    def click_chats_sidebar_button(self) -> None:
        """
        Clicks the "Chats" sidebar button to reach Chats dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_chats_button))
        element.click()
        logging.debug('Clicked "Chats" in Sidebar')

    def click_channels_sidebar_button(self) -> None:
        """
        Clicks the "Channels" sidebar button to reach Channels dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_channels_button))
        element.click()
        logging.debug('Clicked "Channel" in Sidebar')

    def click_status_sidebar_button(self) -> None:
        """
        Clicks the "Status" sidebar button to reach Status dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_status_button))
        element.click()
        logging.debug('Clicked "Status" in Sidebar')

    def click_settings_sidebar_button(self) -> None:
        """
        Clicks the "Settings" sidebar button to reach WhatsApp application settings page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_settings_button))
        element.click()
        logging.debug('Clicked "Settings" in Sidebar')

    def click_profile_sidebar_button(self) -> None:
        """
        Clicks the "Profile" sidebar button to reach current user profile page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_profile_button))
        element.click()
        logging.debug('Clicked "Profile" in Sidebar')


class ChatsPage(WhatsAppPage):
    driver = None
    key_element = (
        By.CSS_SELECTOR,
        '#app > div > div.x78zum5.xdt5ytf.x5yr21d > div > div._aigw.x9f619.x1n2onr6.x5yr21d.x17dzmu4.x1i1dayz.x2ipvbc.x1w8yi2h.x78zum5.xdt5ytf.xa1v5g2.x1plvlek.xryxfnj.xd32934.x1m6msm > header > header > div > div.x104kibb.x1iyjqo2.x4osyxg.x1198e8h.x6ikm8r.x10wlt62.x1mzt3pk.xo442l1.x1ua5tub.x117nqv4.x1aueamr.x1wm35g.xj8l9r2 > h1'
    )
    xpath_opened_chat = '//div[@id="main"]//header//span[text()="{name}"]'
    # Side Buttons
    by_menu_button = (
        By.XPATH,
        '//div[contains(@class,"_aigw")]//header//button[@role="button" and .//span[starts-with(@data-icon,"menu")]]'
    )
    by_new_chat_button = (
        By.XPATH,
        '//div[contains(@class,"_aigw")]//header//button[@role="button" and .//span[starts-with(@data-icon,"new-chat")]]'
    )
    by_search_box = (
        By.XPATH,
        '(//div[@id="side"]//div[@contenteditable="true" and @role="textbox"])[1]'
    )
    # Main / App Buttons
    by_input_box = (
        By.XPATH,
        '(//div[@id="main"]//div[@contenteditable="true" and @role="textbox"])[1]'
    )
    by_input_box_popup = (
        By.XPATH,
        '(//div[@id="main"]//div[@contenteditable="true" and @role="textbox"]//p[contains(@class,"selectable-text") and contains(@class,"copyable-text")])[1]'
    )
    by_chat_submenu_button = (
        By.XPATH,
        '//*[@id="main"]//footer//button[.//span[starts-with(@data-icon,"plus")]]'
    )
    by_chat_submenu_poll_button = (
        By.XPATH,
        '//*[@id="app"]//li[.//*[local-name()="path" and @fill="var(--attachment-type-polls-color)"]]'
    )
    by_chat_submenu_upload_images = (
        By.XPATH,
        '//*[@id="app"]//*[local-name()="input" and @multiple and @type="file" and @accept="image/*,video/mp4,video/3gpp,video/quicktime"]'
    )
    by_chat_send_button = (
        By.XPATH,
        '(//*[@id="app"]//div[./span[starts-with(@data-icon,"send")]])[1]'
    )
    # Poll Entries / Elements
    by_new_poll_popup = (
        By.XPATH,
        '//*[@id="app"]//div[@data-animate-modal-popup="true"]'
    )
    by_new_poll_title = (
        By.XPATH,
        '(//div[@id="app"]//div[@data-animate-modal-popup="true"]//div[@contenteditable="true" and @role="textbox"])[1]'
    )
    by_new_poll_entries = (
        By.XPATH,
        '(//div[@id="app"]//div[@data-animate-modal-popup="true"]//div[@contenteditable="true" and @role="textbox"])[position() > 1]'
    )
    by_new_poll_multi_switch = (
        By.XPATH,
        '//div[@id="app"]//div[@data-animate-modal-popup="true"]//div[@role="switch"]'
    )
    by_new_poll_send_button = (
        By.XPATH,
        '(//*[@id="app"]//div[@data-animate-modal-popup="true"]//div[./span[starts-with(@data-icon,"send")]])[1]'
    )

    def __init__(self, driver: WebDriver):
        super().__init__(driver)
        if driver is None:
            self.driver = driver

        self.driver = driver

    def click_menu_button(self) -> None:
        """
        Clicks the "Menu" panel button.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_menu_button))
        element.click()
        logging.debug('Clicked "Menu" in Chat Panel')

    def click_new_chat_button(self) -> None:
        """
        Clicks the "New Conversation" panel button to start a new conversation workflow.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_new_chat_button))
        element.click()
        logging.debug('Clicked "New Chat" in Chat Panel')

    def click_new_poll_button(self) -> None:
        """
        Clicks the "New Conversation" panel button to start a new conversation workflow.

        :return: None
        """
        # Open the submenu first as creating a new Poll is not a exposed action
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_button))
        element.click()
        logging.debug('Clicked "Chat \'+\'" in Chat Panel')

        # Select the new Poll entry
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_poll_button))
        element.click()
        logging.debug('Clicked "New Poll" in Chat Panel')

    def fill_poll(self, title: str, entries: list[str], multi: bool) -> None:
        """

        :param title:
        :param entries:
        :param multi:
        :return:
        """

        if not title:
            raise ValueError("Poll title must not be empty.")
        elif len(entries) < 2 or len(entries) > 12:
            raise ValueError("Poll must have between 2 and 12 entries.")

        # Type text message
        # TODO: Implement poll title cleanup
        element_title = self.wait.until(EC.visibility_of_element_located(self.by_new_poll_title))
        element_title.send_keys(title)
        logging.debug(f"Added Title entry: {title} in Poll Popup")
        del element_title

        # Type il all entries
        i = 0
        for entry in entries:
            element_entries = self.wait.until(EC.visibility_of_all_elements_located(self.by_new_poll_entries))
            element_entry = element_entries[i]
            # TODO: Implement poll entry cleanup
            element_entry.send_keys(entry)
            logging.debug(f"Added Poll entry: {entry} in Poll Popup")
            i = i + 1

        # Set Multi-Answer
        element_multi = self.wait.until(EC.element_to_be_clickable(self.by_new_poll_multi_switch))
        # Enable switch
        if multi and element_multi.get_attribute("aria-checked") == "false":
            element_multi.click()
            logging.debug(f"Enabled multi-answer in Poll Popup")
        # Disable switch
        elif not multi and element_multi.get_attribute("aria-checked") == "true":
            element_multi.click()
            logging.debug(f"Disabled multi-answer in Poll Popup")
        else:
            logging.debug(f"Poll Multi-answer already configured properly in Poll Popup")
        del element_multi

        element_send = self.wait.until(EC.element_to_be_clickable(self.by_new_poll_send_button))
        element_send.click()
        logging.debug('Clicked "Send Poll Chat" in Poll Popup')
        del element_send

        # Wait until the focus is given back to the input window
        self.wait.until(EC.none_of(EC.presence_of_element_located(self.by_new_poll_popup)))
        logging.debug('Waited for Poll Popup to disappear')

    def send_poll(self, to: str, title: str, entries: list[str], multi: bool) -> None:
        # Find target group or user in the list
        self.find_by_name(to)
        # Open the "New Poll" popup
        self.click_new_poll_button()
        # Send Poll
        self.fill_poll(title, entries, multi)

    def clear_search_box(self):
        """
        Clears the search bar.

        :return: None
        """
        search_box = self.wait.until(
            EC.presence_of_element_located(self.by_search_box))
        search_box.click()
        search_box.send_keys(Keys.CONTROL + 'a')
        search_box.send_keys(Keys.BACKSPACE)
        logging.debug('Cleared "Search Bar" in Chat Panel')

    def find_by_name(self, name: str) -> bool:
        """
        Uses the search bar to find a user chat or a group chat by name.

        :param name: The name of the chat to search for.
        :return: True if the chat was found, False otherwise.
        """
        search_box = self.wait.until(
            EC.presence_of_element_located(self.by_search_box)
        )
        self.clear_search_box()
        search_box.send_keys(name)
        search_box.send_keys(Keys.ENTER)
        logging.debug('Entered new search for text "{name}" in "Search Bar" in Chat Panel'.format(name=name))
        try:
            # Check exact profile was found
            opened_chat = self.shortwait.until(
                EC.presence_of_element_located((By.XPATH, self.xpath_opened_chat.format(name=name)))
            )
            if opened_chat:
                logging.info(f'Successfully fetched chat "{name}"')
                return True
        except TimeoutException:
            logging.info(f'Could not find chat "{name}"')
            return False

    def clear_input_box(self, locator: Tuple[str, str]):
        """
        Clears the input box for messaging.

        :return: None
        """
        input_box = self.wait.until(
            EC.presence_of_element_located(locator))
        input_box.click()
        input_box.send_keys(Keys.CONTROL + 'a')
        input_box.send_keys(Keys.BACKSPACE)
        logging.debug('Cleared "Input Box" in Chat Panel')

    def send_message(self, to: str, text: str, images: list[Path]) -> None:
        """
        Send a text message to a specific user.
        Images may be added as attachments.

        :param to: Target group or username
        :param text: Message to send
        :param images: List of files to attach
        :return: None
        """
        # Find target group or user in the list
        self.find_by_name(to)

        # Get the focus on the input
        self.clear_input_box(self.by_input_box)
        input_box = self.wait.until(EC.presence_of_element_located(self.by_input_box))
        input_box.send_keys(text)
        time.sleep(1)

        # Append images if necessary then Submit using button
        # or Submit using "ENTER" keypress
        if images and len(images) > 0:
            # Open the submenu first as creating a new Poll is not a exposed action
            element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_button))
            element.click()
            logging.debug('Clicked "Chat \'+\'" in Chat Panel')

            # Get the input field
            input_images = self.wait.until(
                EC.presence_of_element_located(self.by_chat_submenu_upload_images)
            )
            # Add images to the input field
            for image in images:
                input_images.send_keys(Path(image).as_posix())
                # Wait until upload is finished
                self.wait.until(
                    EC.visibility_of_element_located(self.by_chat_send_button)
                )
            # Send using button
            send_element = self.wait.until(
                EC.visibility_of_element_located(self.by_chat_send_button)
            )
            send_element.click()

        else:
            # Send using keypress
            input_box.send_keys(Keys.ENTER)