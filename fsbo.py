import time
import random
import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import asyncio
import nest_asyncio
from pyppeteer import launch
from concurrent.futures import ThreadPoolExecutor

# Patch the event loop to work with Streamlit's async environment
nest_asyncio.apply()

# ------------------------------
# Logging configuration
# ------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# ------------------------------
# User-Agent rotation (list of common user agents)
# ------------------------------
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:50.0) Gecko/20100101 Firefox/50.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
]

# ------------------------------
# Authentication function
# ------------------------------
def authenticate():
    """
    Authenticate the user using Streamlit secrets if available,
    otherwise fallback to a hardcoded password.
    """
    # Default password fallback
    default_password = "heLLoRonnie!!"

    # Use Streamlit secrets if defined
    try:
        secret_password = st.secrets["password"]
    except KeyError:
        secret_password = default_password

    password = st.text_input("Enter password", type="password")
    if password == secret_password:
        return True
    elif password != "":
        st.error("Incorrect password!")
    return False

# ------------------------------
# Get user input
# ------------------------------
def get_user_input():
    pages_to_scrape = st.number_input("Number of pages to scrape", min_value=1, max_value=20, value=5)

    apply_filters = st.selectbox("Apply additional filters?", ["No", "Yes"])
    filters = {}

    if apply_filters == "Yes":
        filters['price'] = st.text_input("Price range (min,max), e.g., 200000,500000")
        filters['sqft'] = st.text_input("Square footage range (min,max), e.g., 1500,3000")
        filters['beds'] = st.text_input("Bedrooms range (min,max), e.g., 3,5")

    return pages_to_scrape, filters

# ------------------------------
# Scraping function using Pyppeteer (Headless Chrome)
# ------------------------------
async def scrape_page_with_pyppeteer(url):
    """
    Scrape Zillow FSBO listings from the given URL using pyppeteer (Headless Chrome).
    Returns a list of listings.
    """
    try:
        # Launching headless browser
        browser = await launch(headless=True)
        page = await browser.newPage()

        # Set the user-agent
        user_agent = random.choice(user_agents)
        await page.setUserAgent(user_agent)

        await page.goto(url)  # Visit the page
        await page.waitForSelector('article.list-card')  # Wait for listings to load

        # Get page content
        content = await page.content()

        soup = BeautifulSoup(content, 'html.parser')
        listings = soup.find_all('article', class_='list-card')

        if not listings:
            logger.warning("No listings found on the page.")
            return []

        data = []
        for listing in listings:
            try:
                address = listing.find('address').get_text() if listing.find('address') else "N/A"
                price = listing.find('div', class_='list-card-price').get_text() if listing.find('div', class_='list-card-price') else "N/A"
                link = listing.find('a', class_='list-card-link')['href'] if listing.find('a', class_='list-card-link') else "N/A"
                details = listing.find('ul', class_='list-card-details')
                bedrooms = details.find_all('li')[0].get_text() if details else "N/A"
                bathrooms = details.find_all('li')[1].get_text() if details and len(details.find_all('li')) > 1 else "N/A"
                sqft = details.find_all('li')[2].get_text() if details and len(details.find_all('li')) > 2 else "N/A"

                data.append([address, price, link, bedrooms, bathrooms, sqft])
            except Exception as e:
                logger.error(f"Error parsing a listing: {e}")

        logger.info(f"Scraped {len(data)} listings from this page.")
        await browser.close()
        return data

    except Exception as e:
        logger.error(f"Failed to scrape with Pyppeteer: {e}")
        return []

# ------------------------------
# Function to run the scraper in a separate thread
# ------------------------------
def run_scraper(url):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(scrape_page_with_pyppeteer(url))

# ------------------------------
# Main Streamlit App
# ------------------------------
def main():
    if not authenticate():
        st.stop()

    st.title("Zillow FSBO Scraper - Charlotte, NC")
    st.write("Scrape FSBO listings with optional filters and download as CSV.")

    pages_to_scrape, filters = get_user_input()

    base_url = (
        "https://www.zillow.com/charlotte-nc/fsbo/?searchQueryState=%7B%22isMapVisible%22%3Atrue"
        "%2C%22mapBounds%22%3A%7B%22north%22%3A35.42067033258255%2C%22south%22%3A34.997658980767916"
        "%2C%22east%22%3A-80.51206433886718%2C%22west%22%3A-81.1506446611328%7D%2C%22filterState%22"
        "%3A%7B%22sort%22%3A%7B%22value%22%3A%22globalrelevanceex%22%7D%2C%22fsba%22%3A%7B%22value%22%3Afalse%7D"
        "%2C%22nc%22%3A%7B%22value%22%3Afalse%7D%2C%22cmsn%22%3A%7B%22value%22%3Afalse%7D"
        "%2C%22auc%22%3A%7B%22value%22%3Afalse%7D%2C%22fore%22%3A%7B%22value%22%3Afalse%7D%7D"
        "%2C%22category%22%3A%22cat2%22%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A11"
        "%2C%22usersSearchTerm%22%3A%22Charlotte%2C%20NC%22%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A24043%2C%22regionType%22%3A6%7D%5D%7D"
    )

    all_data = []

    if st.button("Start Scraping"):
        with st.spinner("Scraping... Please wait, this may take several minutes."):
            with ThreadPoolExecutor() as executor:
                for page_num in range(1, pages_to_scrape + 1):
                    page_url = f"{base_url}&page={page_num}"
                    page_data = executor.submit(run_scraper, page_url).result()
                    all_data.extend(page_data)

                    # Delay to avoid anti-scraping detection
                    time.sleep(30)

            if all_data:
                df = pd.DataFrame(all_data, columns=["Address", "Price", "Listing URL", "Bedrooms", "Bathrooms", "Square Footage"])
                st.dataframe(df)

                csv = df.to_csv(index=False)
                st.download_button("Download CSV", data=csv, file_name="charlotte_fsbo_listings.csv", mime="text/csv")

                st.success(f"Scraped {len(all_data)} listings successfully!")
            else:
                st.warning("No listings were scraped. Check the URL or network connection.")

# ------------------------------
# Run the app
# ------------------------------
if __name__ == "__main__":
    main()
