from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from RPA.Robocorp.WorkItems import WorkItems
import re
import json, os
from datetime import datetime, timedelta
import pandas as pd
from robocorp.tasks import task

class NewsScraper:
    def __init__(self):
        # Initialize libraries
        self.browser = Selenium()
        self.excel = Files()
        self.work_items = WorkItems()

        # Variables to be loaded from work items
        self.search_phrase = None
        self.category = None
        self.months = None

        # Output file
        self.excel_file = "news_data.xlsx"

    def load_work_items(self):
        """Load the work items and extract the parameters."""
        # with open("workitem.json", "r") as file:
        #     data = json.load(file)
        #     self.search_phrase = data["variables"]["search_phrase"]
        #     self.category = data["variables"]["category"]
        #     self.months = data["variables"]["months"]

        #     self.output_folder = "output"
        #     self.excel_file = os.path.join(self.output_folder, "news_data.xlsx")
        #     os.makedirs(self.output_folder, exist_ok=True)
        self.work_items.get_input_work_item()

        # Get the parameters from the work item payload
        self.search_phrase = self.work_items.get_variable("search_phrase")
        self.category = self.work_items.get_variable("category")
        self.months = self.work_items.get_variable("months")


    def open_website(self):
        """Open the Gothamist website with the search query."""
        url = f"https://gothamist.com/search?q={self.search_phrase}"
        self.browser.open_available_browser(url)


    def scrape_news(self):
        """Scrape the news data such as title, date, description, and image filename."""
        self.browser.wait_until_element_is_visible('//*[@id="resultList"]', timeout=10)

        # Find the articles using XPath
        articles = self.browser.find_elements('//*[@id="resultList"]/div[2]/div')

        news_data = []
        for index, article in enumerate(articles, start=1):
            # Construct CSS selectors dynamically for each article
            title_xpath = f'//*[@id="resultList"]/div[2]/div[{index}]/div/div[2]/div[1]/a/div'
            description_xpath = f'//*[@id="resultList"]/div[2]/div[{index}]/div/div[2]/div[2]/p'
            image_xpath = f'//*[@id="resultList"]/div[2]/div[{index}]/div/div[1]/figure[2]/div/div/a/div/img'
            link_xpath = f'//*[@id="resultList"]/div[2]/div[{index}]/div/div[2]/div[1]/a'

            # Extract title, description, and image URL
            title = self.browser.get_text(title_xpath)
            description = self.browser.get_text(description_xpath)
            image_url = self.browser.get_element_attribute(image_xpath, "src")

            # Follow the link to get the date
            news_url = self.browser.get_element_attribute(link_xpath, "href")
            date = self.scrape_news_date(news_url)

            # Check if the date is within the required time period based on self.months
            if not self.is_news_within_date_range(date):
                print(f"News {title} is out of time range. Stopping the scraper.")
                break

            # Count of search phrases in title and description
            search_phrase_count = title.lower().count(self.search_phrase.lower()) + description.lower().count(self.search_phrase.lower())

            # Check if any money-related terms are in the title or description
            money_in_text = self.contains_money(title) or self.contains_money(description)

            self.browser.go_back()
            self.browser.wait_until_element_is_visible('//*[@id="resultList"]', timeout=10)


            # Save data for each news article
            news_data.append({
                "title": title,
                "date": date.strftime("%Y-%m-%d"),  # Format date as a string
                "description": description,
                "image_url": image_url,
                "search_phrase_count": search_phrase_count,
                "contains_money": money_in_text
            })

        return news_data


    def scrape_news_date(self, news_url):
        """Visit the individual news link and scrape the publication date."""
        self.browser.go_to(news_url)

        # Wait until the date element is visible
        date_selector = f'//*[@id="__nuxt"]/div/div/main/div[2]/section[1]/div/div[2]/div[2]/div[2]/div/div[1]/div[2]/div[2]/p'
        self.browser.wait_until_element_is_visible(date_selector, timeout=10)

        date_text = self.browser.get_text(date_selector)  # "Published Dec 6, 2023"
        date_text = date_text.replace("Published ", "")  # Remove "Published" from the string

        # Convert to datetime object
        date = datetime.strptime(date_text, "%b %d, %Y")
        return date


    def is_news_within_date_range(self, date):
        """Check if the news date is within the required time period."""
        current_date = datetime.now()

        # Calculate the earliest date to include news from
        if self.months == 0 or self.months == 1:
            start_date = current_date.replace(day=1)  # Start from the first day of the current month
        else:
            # Start date is calculated by subtracting the number of months
            first_of_current_month = current_date.replace(day=1)
            start_date = first_of_current_month - timedelta(days=30 * (self.months - 1))  # Approximate days in a month

        return start_date <= date <= current_date


    def save_to_excel(self, news_data):
        """Save the scraped news data to an Excel file using RPA.Excel.Files."""
        # Ensure the output folder exists
        os.makedirs(self.output_folder, exist_ok=True)

        # Create a new workbook
        self.excel.create_workbook(self.excel_file)

        # Add headers to the first row
        headers = ["Title", "Date", "Description", "Image URL", "Search Phrase Count", "Contains Money"]
        self.excel.append_rows_to_worksheet([headers], header=True)

        # Add the news data rows
        for data in news_data:
            row = [
                data["title"],
                data["date"],
                data["description"],
                data["image_url"],
                data["search_phrase_count"],
                data["contains_money"]
            ]
            self.excel.append_rows_to_worksheet([row], header=False)

        # Save and close the workbook
        self.excel.save_workbook()
        self.excel.close_workbook()


    def contains_money(self, text):
        """Check if the text contains money-related terms."""
        pattern = r'\$\d+(\.\d{1,2})?|USD|\d+ dollars'
        return bool(re.search(pattern, text))


    def run(self):
        """Run the scraper."""
        self.load_work_items()
        self.open_website()
        news_data = self.scrape_news()
        self.save_to_excel(news_data)

        # Complete the work item
        self.work_items.complete_work_item()


    def close(self):
        """Close the browser."""
        self.browser.close_all_browsers()

@task
def scraper():
    scraper = NewsScraper()
    try:
        scraper.run()
    finally:
        scraper.close()
