"""
Kindercare-specific implementation of school scraping and enrichment.
"""
import re
import time
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from base.base_scraper import BaseSchoolScraper, BaseSchoolEnricher

class KindercareSchoolScraper(BaseSchoolScraper):
    """Implementation of school scraper for Kindercare schools."""
    
    def __init__(self, headless: bool = False):
        super().__init__(headless)
        self.base_url = "https://www.kindercare.com/our-centers/results"
        self.program_filter_xpaths = [
            # Fieldset 1
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[1]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[2]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[3]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[4]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[5]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[6]/label[1]",
            "//*[@id='main']//div[1]/fieldset[1]/ol[1]/li[7]/label[1]",
            # Fieldset 2
            "//*[@id='main']//div[1]/fieldset[2]/ol[1]/li[1]/label[1]",
            "//*[@id='main']//div[1]/fieldset[2]/ol[1]/li[2]/label[1]",
            "//*[@id='main']//div[1]/fieldset[2]/ol[1]/li[3]/label[1]"
        ]

    def apply_filters(self, filters: List[str]):
        """Apply Kindercare-specific filters to the school search."""
        self.driver.get(self.base_url)
        
        # Wait for page to load (10 seconds as per Mozenda)
        time.sleep(10)

        # Click each filter in sequence
        for xpath in self.program_filter_xpaths:
            try:
                element = self.wait_for_element(By.XPATH, xpath, condition="clickable")
                if element:
                    element.click()
                    time.sleep(1)  # 1 second wait after each click as per Mozenda
            except Exception as e:
                self.logger.warning(f"Failed to click filter {xpath}: {str(e)}")

    def _get_school_urls(self, location: str) -> List[str]:
        """Get all school URLs for a given location."""
        try:
            # Enter location in search box
            location_input = self.wait_for_element(
                By.XPATH, 
                "//*[@id='center-search-location']",
                condition="clickable"
            )
            location_input.clear()
            location_input.send_keys(location)

            # Click search button
            search_button = self.wait_for_element(
                By.XPATH,
                "//*[@id='main']//li[3]/button[1]",
                condition="clickable"
            )
            search_button.click()

            # Wait for results (10 seconds + 2 seconds for AJAX as per Mozenda)
            time.sleep(12)

            # Get all school URLs using the exact XPath from Mozenda
            links = self.driver.find_elements(
                By.XPATH,
                "//*[@id='main']//article[1]/ol[1]/li/div[1]/a[1]"
            )
            return [link.get_attribute("href") for link in links]

        except Exception as e:
            self.logger.error(f"Error getting school URLs: {str(e)}")
            return []

    def _extract_school_data(self, url: str) -> Optional[Dict]:
        """Extract data for a single school."""
        try:
            self.driver.get(url)
            time.sleep(10)  # Wait as per Mozenda configuration

            # Initialize school data dictionary
            school_data = {
                "url": url,
                "name": None,
                "phone": None,
                "ages": None,
                "address1": None,
                "address2": None,
                "city": None,
                "state": None,
                "zip": None,
                "hours": None,
                "director": None
            }

            # Extract data using exact Mozenda XPaths
            xpaths = {
                "name": "//*[@id='cdp-overview']/h1[1]",
                "phone": "//*[@id='cdp-overview']/div[4]/a[2]/span[1]",
                "ages": "//*[@id='cdp-overview']/div[3]/div[2]",
                "address": "//*[@id='cdp-overview']/div[3]/div[1]",
                "hours": "//*[@id='cdp-overview']/div[3]/div[3]",
                "director": "//*[@id='cdp-overview']/div[3]/div[4]"
            }

            # Extract each field
            for field, xpath in xpaths.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    if field == "address":
                        # Use Mozenda's regex patterns for address parsing
                        address_text = element.text
                        address_pattern = r"Address:\s*(.+?)\n\s*(.+?),\s*([A-Z]{2})\s*(\d{5}(-\d{4})?)"
                        match = re.search(address_pattern, address_text)
                        if match:
                            school_data["address1"] = match.group(1)
                            school_data["city"] = match.group(2)
                            school_data["state"] = match.group(3)
                            school_data["zip"] = match.group(4)
                    else:
                        school_data[field] = element.text.strip()
                except:
                    self.logger.warning(f"Could not extract {field}")

            # Extract program availability
            availability_xpaths = {
                "infant": "//*[@id='main']//aside[1]/section[2]/div[1]/div[1]",
                "toddler": "//*[@id='main']//section[2]/div[1]/div[2]",
                "discovery_preschool": "//*[@id='main']//section[2]/div[1]/div[3]",
                "preschool": "//*[@id='main']//section[2]/div[1]/div[4]",
                "prekindergarten": "//*[@id='main']//section[2]/div[1]/div[5]",
                "kindergarten": "//*[@id='main']//section[2]/div[1]/div[6]",
                "before_after_school": "//*[@id='main']//section[2]/div[1]/div[7]"
            }

            for program, xpath in availability_xpaths.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    availability = "Available" if "available" in element.text.lower() else "Not Available"
                    school_data[f"availability_{program}"] = availability
                except:
                    school_data[f"availability_{program}"] = "Unknown"

            return school_data

        except Exception as e:
            self.logger.error(f"Error extracting school data from {url}: {str(e)}")
            return None

    def get_table_data(self):
        """Extract school data from all locations."""
        # Alaska zip codes
        alaska_zips = [
            "33127"
        ]

        all_urls = set()
        for zip_code in alaska_zips:
            urls = self._get_school_urls(zip_code)
            all_urls.update(urls)

        # Process each school
        for url in all_urls:
            if url not in self.processed_urls:
                school_data = self._extract_school_data(url)
                if school_data:
                    self.schools_data.append(school_data)
                    self.processed_urls.add(url)
                    self.logger.info(f"Processed school: {school_data['name']}")

    def run(self, filters: List[str], output_file: str):
        """Execute the Kindercare school scraping process."""
        try:
            self.setup_driver()
            self.apply_filters(filters)
            self.get_table_data()
            self.save_data(output_file)
            self.logger.info("Scraping completed successfully")
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
        finally:
            self.cleanup()


if __name__ == "__main__":
    # Example usage
    scraper = KindercareSchoolScraper()
    scraper.run(
        filters=[],  # No additional filters needed as we handle them in apply_filters
        output_file="kindercare_schools_data.csv"
    )