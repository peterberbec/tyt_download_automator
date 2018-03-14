import os
import re
import sys
from pathlib import Path

import requests
from logzero import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


driver = webdriver.Firefox()


class BasePage(object):
    """Base class for the page that will be interacted with"""

    def __init__(self):
        self.driver = driver


class MainPage(BasePage):
    """The main page of the site"""

    def go(self):
        """Open the browser and navigate to the page"""
        self.driver.get("https://tytnetwork.com/")

    def click_login_button(self):
        """Click the button that takes you to the login page"""
        login_button = self.driver.find_element_by_xpath("//li/a[span/text()='Log In']")
        login_button.click()
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "user_login"))
            )
        except TimeoutException:
            self.driver.quit()
            sys.exit("Login fields never loaded")
        return LoginPage()

    def click_logout_button(self):
        """Click the button that logs you out"""
        logout_button = self.driver.find_element_by_xpath("//li/a[span/text()='Log Out']")
        logout_button.click()

    def get_episode_page_links(self):
        """Get the episode permalinks visible on the current page"""
        path = (
            ".//div[@id='x-section-2']"
            "/div[@class='x-container max width']"
            "/div[@class='x-column x-sm cs-ta-left x-1-1']"
        )
        episode_container = self.driver.find_element_by_xpath(path)
        link_tags = episode_container.find_elements_by_xpath(".//h3[@class='rpwe-title']/a")
        episode_links = [tag.get_attribute("href") for tag in link_tags]
        return episode_links


class LoginPage(BasePage):
    """The login page"""

    def enter_credentials(self):
        username = os.environ['TYT_USERNAME']
        password = os.environ['TYT_PASSWORD']
        username_field = self.driver.find_element_by_id("user_login")
        password_field = self.driver.find_element_by_id("user_pass")
        submit_button = self.driver.find_element_by_xpath("//input[@type='submit']")

        username_field.send_keys(username)
        password_field.send_keys(password)
        submit_button.click()


class EpisodePage(BasePage):
    """The page for an individual episode"""

    def __init__(self, url):
        super().__init__()
        self.driver.get(url)

    def get_download_details(self):
        try:
            link = self.driver.find_element_by_xpath("//a[text()='Download Video']")
        except NoSuchElementException:
            return (None, None)
        url = link.get_attribute("href")
        filename = link.get_attribute("download")
        return (url, filename)


class Downloader(object):
    """Handles downloading and organizing episodes"""

    def __init__(self):
        download_folder = os.environ['TYT_DOWNLOAD_FOLDER']
        self.download_queue = []
        self.download_root = Path(download_folder)

    def add_to_queue(self, ep):
        self.download_queue.append(ep)

    def process_download_queue(self):
        for item in self.download_queue:
            folder_path = self.download_root / item.folder_name
            folder_path.mkdir(exist_ok=True)
            download_path = folder_path / item.filename
            if download_path.exists():
                logger.info(f"File '{item.filename}' previously downloaded, skipping...")
                continue
            req = requests.get(item.url, stream=True)
            logger.info(f"Downloading file '{item.filename}'...")
            with download_path.open('wb') as dwn:
                for chunk in req.iter_content(chunk_size=1024):
                    dwn.write(chunk)
            logger.info("...Done")


class QueuedDownload(object):
    """Contains the information for a file to be downloaded"""

    def __init__(self, url, filename):
        self.url = url
        folder, storage_filename = self.parse_download_filename(filename)
        self.folder_name = folder
        self.filename = storage_filename

    @staticmethod
    def parse_download_filename(filename):
        """Extracts date information from the download filename"""
        show_codes = {
            "TA": "TYT Hour 1",
            "TB": "TYT Hour 2",
            "PG": "TYT Postgame",
            "HQ": "Rebel HQ",
            "MF": "Murder with Friends",
            "AP": "Aggressive Progressives",
            "NA": "Nerd Alert",
            "OS": "Old School",
            "IN": "TYT Interviews",
            "RI": "Reporting In",
            "OT": "Overtime",
            "BITS": "Behind the Scenes",
            "EL": "Election Coverage",
            "MC": "The News with Dan Rather",
            "PGC": "TYT Classics",
        }
        match = re.search(r"(\d{2})(\d{2})(\d{2})__(\w{2}).*\.mp4", filename)
        assert match is not None, "Couldn't parse filename"
        year, month, day, show = match.group(1, 2, 3, 4)
        formatted_filename = f"20{year}-{month}-{day} - {show_codes[show]}.mp4"
        folder_name = f"20{year}-{month}-{day}"
        return folder_name, formatted_filename
