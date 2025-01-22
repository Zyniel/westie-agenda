import base64
import logging
import os
import shutil
from datetime import time
from enum import Enum
from pathlib import Path
import time
from typing import Tuple
import subprocess
from sys import platform

import undetected_chromedriver as uc
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService
from undetected_chromedriver import WebElement
from webdriver_manager.chrome import ChromeDriverManager

__doc__ = "WhatsApp Web custom client."

log = logging.getLogger('com.zyniel.dance.westie-agenda.whatsapp-client')
logging.basicConfig(level=logging.DEBUG)

if [os.getenv('VIRTUAL_DISPLAY') is not None and os.getenv('VIRTUAL_DISPLAY') == 1]:
    from pyvirtualdisplay import Display
    display = Display(visible=False, size=(1920, 1080))
    display.start()

def copy2clip(text: str):
    """Copy text to the clipboard."""
    match os := platform.system():
        case "Windows":
            cmd = "clip"
        case "Darwin":
            cmd = "pbcopy"
        case "Linux" | "FreeBSD":
            for cmd in ("xclip", "xsel"):
                if shutil.which(cmd):
                    break
            else:
                raise NotImplementedError(
                    f"If your {os} machine does not use xclip or xsel, please "
                    "use 'pyperclip' PyPi to copy text to the clipboard."
                )
        case _:
            raise NotImplementedError(f"Operating system {os} is not supported.")

    subprocess.run(cmd, text=True, check=False, input=text)

# class syntax
class AppPage(Enum):
    STARTUP = 1
    LOGIN = 2
    LOADING = 3
    MAIN = 4
    UNKNOWN = 99


class WhatsAppLoginHandler(object):
    qrcode = None
    config = None

    def __init__(self, config):
        self.config = config

    def notify(self):
        pass


class WhatsAppWebClient(object):
    browser = None
    config = None
    wait = None
    notifiers : list[WhatsAppLoginHandler] = []

    by_initial_startup = (
        By.ID,
        'wa_web_initial_startup'
    )
    by_auth_page = (
        By.CSS_SELECTOR,
        'input#auto-logout-toggle'
    )
    by_loading_page = (
        By.XPATH,
        '//progress[@max="100"]'
    )
    by_qrcode_refreshed = (
        By.XPATH,
        "//div[@data-ref and .//canvas]"
    )
    by_qrcode_refresh_button = (
        By.XPATH,
        "//div[@data-ref]//button"
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
        self.chrome_options = uc.ChromeOptions()

        # Add your options as needed
        options = [
            # Define window size here
            "--window-size=1920,1080",
            "--ignore-certificate-errors",
            "--disable-infobars",
            "start-maximized",
            "--disable-extensions",
            "--disable-gpu",
            "--no-sandbox",
            # "--headless",
            # "--ignore-certificate-errors",
            # "--disable-extensions",
            # "--disable-dev-shm-usage",
            # '--remote-debugging-port=9222'
        ]

        for option in options:
            self.chrome_options.add_argument(option)

        if self.config['chrome']['user_dir_folder']:
            user_dir = Path(self.config['chrome']['user_dir_folder']).absolute().as_posix()
            self.chrome_options.add_argument("--user-data-dir=" + user_dir)

    def startup(self):
        # setup Edge Driver
        self.browser = uc.Chrome(version_main= 131, options=self.chrome_options, service=ChromeService(ChromeDriverManager().install()))
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
        self.browser.get("https://web.whatsapp.com/")
        self.browser.maximize_window()

        logged = False
        retries = 20
        retry = 1
        while not logged and retry <= retries:
            try:
                # Wait until Main Page or Login Page has been reached
                log.info('Checking WhatsApp Web authentication status :')
                element_page = self.wait.until(EC.any_of(
                    EC.visibility_of_element_located(self.by_auth_page),
                    EC.visibility_of_element_located(self.by_main_page)))

                current_page = self.check_current_page()

                if current_page == AppPage.MAIN:
                    log.info('> Already logged in !')
                    logged = True
                elif current_page == AppPage.LOGIN:
                    log.info('> Not logged. Proceeding to QR Code dispatch.')

                    # Wait until the QR code image is located
                    # QR code needs refresh
                    try:
                        qr_button = self.browser.find_element(*self.by_qrcode_refresh_button)
                        log.info('QR Code needs refresh. Requesting new QR code.')
                        qr_button.click()
                        log.info('Waiting for refresh.')
                        # TODO: Identify the "In reload div ... but too fast ..."
                        time.sleep(5)
                        page = self.wait.until(EC.visibility_of_element_located(self.by_qrcode_refreshed))
                        log.info('New QR code available !')

                    except NoSuchElementException as e:
                        log.info('QR code is visible !')

                    # QR code is available
                    qr_div =  self.wait.until(EC.visibility_of_element_located(self.by_qrcode_refreshed))
                    qr_canvas = qr_div.find_element(By.TAG_NAME, 'canvas')
                    qr_code_base64 = qr_canvas.screenshot_as_base64
                    # Save the QR code image to a file
                    qr_code_image_path = "qr_code.png"
                    with open(qr_code_image_path, "wb") as f:
                        f.write(base64.b64decode(qr_code_base64))

                    # Trigger notification listeners
                    for notifier in self.notifiers:
                        path = Path(qr_code_image_path).absolute().as_posix()
                        notifier.qrcode = path
                        notifier.notify()

                else:
                    raise ValueError('Unknown page ! Quitting.')
            except TimeoutException as e:
                log.info(f'Unknown error or QR code analysis. Retrying. ${retry}/${retries}')
            finally:
                retries = retries + 1
                time.sleep(10)


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
        log.debug('Main Page loaded !')

    def _click_communities_sidebar_button(self) -> None:
        """
        Clicks the "Communities" sidebar button to reach Communities dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_communities_button))
        element.click()
        log.debug('Clicked "Communities" in Sidebar')

    def _click_chats_sidebar_button(self) -> None:
        """
        Clicks the "Chats" sidebar button to reach Chats dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_chats_button))
        element.click()
        log.debug('Clicked "Chats" in Sidebar')

    def _click_channels_sidebar_button(self) -> None:
        """
        Clicks the "Channels" sidebar button to reach Channels dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_channels_button))
        element.click()
        log.debug('Clicked "Channel" in Sidebar')

    def _click_status_sidebar_button(self) -> None:
        """
        Clicks the "Status" sidebar button to reach Status dedicated page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_status_button))
        element.click()
        log.debug('Clicked "Status" in Sidebar')

    def _click_settings_sidebar_button(self) -> None:
        """
        Clicks the "Settings" sidebar button to reach WhatsApp application settings page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_settings_button))
        element.click()
        log.debug('Clicked "Settings" in Sidebar')

    def _click_profile_sidebar_button(self) -> None:
        """
        Clicks the "Profile" sidebar button to reach current user profile page.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_profile_button))
        element.click()
        log.debug('Clicked "Profile" in Sidebar')


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
    by_chat_close_draft_button = (
        By.XPATH,
        '(//*[@id="app"]//div[./span[starts-with(@data-icon,"x")]])[1]'
    )
    by_chat_editor_pen_button = (
        By.XPATH,
        '(//*[@id="app"]//div[./span[starts-with(@data-icon,"media-editor-drawing")]])[1]'
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

    def _click_menu_button(self) -> None:
        """
        Clicks the "Menu" panel button.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_menu_button))
        element.click()
        time.sleep(0.20)
        log.debug('--> Clicked "Menu" in Chat Panel')

    def _click_new_chat_button(self) -> None:
        """
        Clicks the "New Conversation" panel button to start a new conversation workflow.

        :return: None
        """
        element = self.wait.until(EC.element_to_be_clickable(self.by_new_chat_button))
        element.click()
        time.sleep(0.20)
        log.debug('--> Clicked "New Chat" in Chat Panel')

    def _click_new_poll_button(self) -> None:
        """
        Clicks the "New Conversation" panel button to start a new conversation workflow.

        :return: None
        """
        # Open the submenu first as creating a new Poll is not a exposed action
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_button))
        element.click()
        time.sleep(0.20)
        log.debug('--> Clicked "Chat \'+\'" in Chat Panel')

        # Select the new Poll entry
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_poll_button))
        element.click()
        time.sleep(0.20)
        log.debug('--> Clicked "New Poll" in Chat Panel')

    def _set_text(self, element: WebElement, text: str) -> None:
        """
        Copy/Paste text into a WebElement to bypass Emoji and DMP character issues using ChromeDriver

        :param element: target element to populate
        :param text: Text to copy/paste
        :return: None
        """

        # Alternative to populate clipboard
        element.click()
        time.sleep(0.20)
        inline_script = f'''
        const text = `{text}`;
        const dataTransfer = new DataTransfer();
        dataTransfer.setData('text', text);
        const event = new ClipboardEvent('paste', {{
          clipboardData: dataTransfer,
          bubbles: true
        }});
        arguments[0].dispatchEvent(event)
        '''
        self.driver.execute_script(inline_script,element)
        element.send_keys('.')
        element.send_keys(Keys.BACKSPACE)
        time.sleep(0.20)

    def _cancel_draft(self):
        # Select the new Poll entry
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_close_draft_button))
        element.click()
        time.sleep(0.20)
        log.debug(f'--> Clicked "X" to close Draft')
        log.info('Removed previous draft')

    def _fill_poll(self, title: str, entries: list[str], multi: bool) -> None:
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
        # element_title.send_keys(title)
        # Handle emojis...
        self._set_text(element_title, title)
        log.debug(f'--> Copy/Pasted text to poll "Title" field.')
        log.info(f"Added Title entry: {title} in Poll Popup")
        del element_title

        # Type in all entries
        i = 0
        for entry in entries:
            inserted = False
            retries = 10
            retry = 1
            while not inserted and retry <= retries:
                try:
                    element_entries = self.wait.until(EC.visibility_of_all_elements_located(self.by_new_poll_entries))
                    element_entry = element_entries[i]
                    # TODO: Implement poll entry cleanup
                    # element_entry.send_keys(entry)
                    # Handle emojis...
                    self._set_text(element_entry, entry)
                    log.debug(f'--> Copy/Pasted text to poll "Entry" field.')
                    log.info(f"Added Poll entry: {entry} in Poll Popup")

                    i = i + 1
                    inserted = True
                except Exception as e:
                    retry = retry + 1
                    time.sleep(0.5)

        # Set Multi-Answer
        element_multi = self.wait.until(EC.element_to_be_clickable(self.by_new_poll_multi_switch))
        # Enable switch
        if multi and element_multi.get_attribute("aria-checked") == "false":
            element_multi.click()
            log.debug(f'--> Clicked and Enabled Slider "Multiple Answers"')
            log.info("Enabled multi-answer in Poll Popup")
        # Disable switch
        elif not multi and element_multi.get_attribute("aria-checked") == "true":
            element_multi.click()
            log.debug(f'--> Clicked and Disabled Slider "Multiple Answers"')
            log.info(f"Disabled multi-answer in Poll Popup")
        else:
            log.debug(f"Poll Multi-answer already configured properly in Poll Popup")
        del element_multi

    def _click_send_poll(self):
        """
        Clicks the "Send poll" button through Web Browser actions

        :return: None
        """
        element_send = self.wait.until(EC.element_to_be_clickable(self.by_new_poll_send_button))
        element_send.click()
        log.debug('--> Clicked "Send Poll Chat" in Poll Popup')
        del element_send

        # Wait until the focus is given back to the input window
        self.wait.until(EC.none_of(EC.presence_of_element_located(self.by_new_poll_popup)))
        time.sleep(2)
        log.debug('--> Waited for Poll Popup to disappear')

    def _click_send_message(self, has_images: bool):
        """
        Clicks the "Send message" button through Web Browser actions

        :return: None
        """
        if has_images:
            # Send using keypress
            element_send = self.wait.until(
                EC.presence_of_element_located(self.by_chat_send_button))
            element_send.click()
            log.debug('--> Clicked "Chat \'>\'" in Chat Panel')

            # Wait until the focus is given back to the input window
            self.wait.until(EC.none_of(EC.presence_of_element_located(self.by_chat_editor_pen_button)))
            time.sleep(2)

        else:
            input_box = self.wait.until(EC.element_to_be_clickable(self.by_input_box))
            input_box.click()
            input_box.send_keys(Keys.ENTER)
            log.debug('Typed "ENTER" to send message in Chat Panel')
            time.sleep(2)

    def _clear_search_box(self):
        """
        Clears the search bar.

        :return: None
        """
        search_box = self.wait.until(
            EC.presence_of_element_located(self.by_search_box))
        search_box.click()
        search_box.send_keys(Keys.CONTROL + 'a')
        search_box.send_keys(Keys.BACKSPACE)
        log.debug('Cleared "Search Bar" in Chat Panel')

    def _find_by_name(self, name: str) -> bool:
        """
        Uses the search bar to find a user chat or a group chat by name.

        :param name: The name of the chat to search for.
        :return: True if the chat was found, False otherwise.
        """
        log.info(f'New User/Group contact search : {name}')
        search_box = self.wait.until(
            EC.presence_of_element_located(self.by_search_box)
        )
        self._clear_search_box()
        log.debug(f'--> Cleared "Search By" input box.')
        search_box.send_keys(name)
        log.debug(f'--> Input text to "Search By" input box.')
        time.sleep(1)
        search_box.send_keys(Keys.ENTER)
        log.debug(f'--> Pressed "ENTER" to submit "Search By"')
        try:
            # Check exact profile was found
            opened_chat = self.wait.until(
                EC.presence_of_element_located((By.XPATH, self.xpath_opened_chat.format(name=name)))
            )
            if opened_chat:
                log.info(f'Found contact "{name}" !')
                return True
        except TimeoutException:
            log.info(f'Could not find contact "{name}" !')
            return False

    def _clear_input_box(self, locator: Tuple[str, str]):
        """
        Clears the input box for messaging.

        :return: None
        """
        input_box = self.wait.until(
            EC.presence_of_element_located(locator))
        input_box.click()
        input_box.send_keys(Keys.CONTROL + 'a')
        input_box.send_keys(Keys.BACKSPACE)

    def _type_message(self, text: str, images: list[Path]) -> None:
        """
        Type a text message to a specific user.
        Images may be added as attachments.

        :param text: Message to send
        :param images: List of files to attach
        :return: None
        """
        # Get the focus on the input
        self._clear_input_box(self.by_input_box)
        log.debug(f'--> Cleared "Message" input box.')

        input_box = self.wait.until(EC.presence_of_element_located(self.by_input_box))
        input_box.click()
        log.debug(f'--> Clicked inside "Message" input box.')
        self._set_text(input_box, text)
        log.debug(f'--> Copy/Pasted text to "Message" input box.')
        # input_box.send_keys(text)
        time.sleep(1)

        # Open the submenu first as creating a new Poll is not a exposed action
        element = self.wait.until(EC.element_to_be_clickable(self.by_chat_submenu_button))
        element.click()
        log.debug('--> Clicked "Chat \'+\'" in Chat Panel')

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
            log.debug(f'--> Injected new image inside! ${image}')

    def search_user_or_group(self, to: str) -> bool:
        """
        Search for a user / group by name. Return True is found, False otherwise.

        :param to: User or group name to search for.
        :return: True is found, False otherwise.
        """
        # Find target group or user in the list
        return self._find_by_name(to)

    def create_and_send_new_poll(self, to: str, title: str, entries: list[str], multi: bool) -> None:
        # Position on Chat Panel
        self._click_chats_sidebar_button()
        # Find recipient and proceed to message input
        if self._find_by_name(to):
            # Get the focus on the input
            self._clear_input_box(self.by_input_box)
            # Open the "New Poll" popup
            self._click_new_poll_button()
            # Fill poll with data
            self._fill_poll(title, entries, multi)
            # Send poll
            self._click_send_poll()
        else:
            log.warning(f"Poll not sent. Could not find group/user: ${to}")

    def create_and_send_new_message(self, to: str, text: str, images: list[Path]) -> None:
        """
        Send a text message to a specific user.
        Images may be added as attachments.

        :param to: Target group or username
        :param text: Message to send
        :param images: List of files to attach
        :return: None
        """
        # Position on Chat Panel
        self._click_chats_sidebar_button()

        # Find recipient and proceed to message input
        if self._find_by_name(to):
            # Get the focus on the input
            self._clear_input_box(self.by_input_box)
            # Type message and attach images (optional)
            self._type_message(text, images)
            # Send message - send mechanic depends on the presence of attachments
            has_images = (images and len(images) > 0)
            self._click_send_message(has_images)
        else:
            log.warning(f"Message not sent. Could not find group/user: ${to}")