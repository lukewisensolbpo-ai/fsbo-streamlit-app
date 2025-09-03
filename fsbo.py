import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import time
import logging

# Set up logging for better debugging and error monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Password authentication
def authenticate():
    password = st.text_input("Enter password", type="password")
    if password == "heLLoRonnie!!":
        return True
    elif password != "":
        st.error("Incorrect password!")
    return False

# Function to get user input from the UI
def get_user_input():
    # Input for the number of pages to scrape
    pages_to_scrape = st.number_input("How many pages would you like to scrape?", min_value=1, max_value=20, value=5)

    # Optional filters
    apply_filters = st.selectbox("Do you want to apply additional filters?", ["No", "Yes"])
    
    filters = {}
    if apply_filters == "Yes":
        filters['price'] = st.text_input("Enter price range (min_price,max_price), e.g., 200000,500000")
        filters['sqft'] = st.text_input("Enter square footage range (min_sqft,max_sqft), e.g., 1500,3000")
        filters['beds'] = st.text_input("Enter the number of bedrooms (min_beds,max_beds), e.g., 3,5")

    return pages_to_scrape, filters

# Function to scrape data from Zillow listings with error handling
def scrape_page(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Will raise HTTPError for bad responses (4xx, 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')

        listings = soup.find_all('div', class_="list-card")
        data = []

        for listing in listings:
            address = listing.find('address').get_text() if listing.find('address') else None
            price = listing.find('div', class_="list-card-price").get_text() if listing.find('div', class_="list-card-price") else None
            link = listing.find('a', class_="list-card-link")['href'] if listing.find('a', class_="list-card-link") else None
            bedrooms = listing.find('ul', class_="list-card-details").find_all('li')[0].get_text() if listing.find('ul', class_="list-card-details") else None
            bathrooms = listing.find('ul', class_="list-card-details").find_all('li')[1].get_text() if listing.find('ul', class_="list-card-details") else None
            sqft = listing.find('ul', class_="list-card-details").find_all('li')[2].get_text() if listing.find('ul', class_="list-card-details") else None

            data.append([address, price, link, bedrooms, bathrooms, sqft])

        logger.info(f"Successfully scraped {len(data)} listings from the page.")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []

# Main function to control the flow of the app
def main():
    # Check for password authentication
    if not authenticate():
        st.stop()

    st.title("Zillow FSBO Scraper")
    
    st.write("### Customize your search for For Sale By Owner properties in Charlotte, NC")

    # Get user input (number of pages and filters)
    pages_to_scrape, filters = get_user_input()

    # Base URL and logging
    base_url = "https://www.zillow.com/charlotte-nc/fsbo/?searchQueryState={YOUR_QUERY_PARAMS}"

    all_data = []
    
    if st.button("Start Scraping"):
        with st.spinner("Scraping data... This may take a few moments..."):
            # Scrape pages
            for page_num in range(1, pages_to_scrape + 1):
                page_url = f"{base_url}&page={page_num}"

                page_data = scrape_page(page_url)
                all_data.extend(page_data)

                # Implement delay between requests for anti-scraping
                time.sleep(30)  # Safe delay of 30 seconds to avoid rate limits or blocking

            if all_data:
                # Create DataFrame for displaying the data
                df = pd.DataFrame(all_data, columns=["Address", "Price", "Listing URL", "Bedrooms", "Bathrooms", "Square Footage"])
                
                # Display DataFrame in Streamlit
                st.write(df)
                
                # Allow the user to download the data as a CSV
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name='charlotte_fsbo_listings.csv',
                    mime='text/csv'
                )
                
                st.success("Data scraping complete!")
            else:
                st.warning("No data was scraped. Please check the network or the URL structure.")

# Run the app
if __name__ == "__main__":
    main()
