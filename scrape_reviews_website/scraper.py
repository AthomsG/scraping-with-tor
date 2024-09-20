import requests
import json
import csv
import time
import random
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
import socket
import socks
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm  # Import tqdm for the progress bar

# Headers to mimic a real browser request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Lock for safe Tor IP renewal
tor_lock = Lock()

# Function to connect to Tor (This part works from your provided script)
def connectTor():
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)
    socket.socket = socks.socksocket

# Function to renew Tor IP (Also works from your script)
def renewTor(controller):
    try:
        with tor_lock:
            controller.authenticate("abc123")  # or simply controller.authenticate() if using cookie-based
            controller.signal(Signal.NEWNYM)
            print("TOR IP renewed successfully")
    except Exception as e:
        print(f"Error renewing TOR IP: {e}")

# Function to show current IP (Just for testing purposes)
def showIP():
    try:
        ip = urlopen('https://icanhazip.com').read().decode().strip()
        print(f"Current IP: {ip}")
    except Exception as e:
        print(f"Error retrieving IP: {e}")

# Function to log errors to a file
def log_error(url, status_code, content=None):
    with open('scraper_errors.log', 'a', encoding='utf-8') as log_file:
        log_file.write(f"Failed to retrieve URL: {url}, Status Code: {status_code}\n")
        if content:
            log_file.write(f"Response content: {content}\n")
        log_file.write("-" * 80 + "\n")  # Divider for better readability

# Function to scrape the user's country from their profile page
def scrape_user_country(profile_link):
    try:
        response = requests.get(profile_link, headers=headers)
        if response.status_code != 200:
            print(f"Failed to retrieve profile page: {profile_link}, Status Code: {response.status_code}")
            log_error(profile_link, response.status_code, response.text)  # Log the error with content
            return None

        # Parse the user's profile page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the country in the user's profile page based on the HTML structure
        country_tag = soup.find('p', attrs={'data-consumer-country-typography': 'true'})
        if country_tag:
            return country_tag.text.strip()  # Return the country name
        else:
            print(f"Country not found for user profile: {profile_link}")
            return None
    except Exception as e:
        print(f"Error scraping country for profile {profile_link}: {e}")
        log_error(profile_link, 'Exception', str(e))  # Log the exception
        return None

# Function to scrape a single page of reviews
def scrape_page(page_number, website):
    url = f'https://www.trustpilot.com/review/{website}?page={page_number}'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 404:
        return None
    
    if response.status_code != 200:
        print(f"Failed to retrieve page {page_number} for website {website}, Status Code: {response.status_code}")
        log_error(url, response.status_code, response.text)  # Log the error with content
        return None

    # Parse the page content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the embedded JSON-LD data in the HTML
    script_tag = soup.find('script', type='application/ld+json')
    if not script_tag:
        print(f"No JSON-LD script tag found on page {page_number} for website {website}")
        log_error(url, 'No JSON-LD', response.text)  # Log the missing JSON-LD error
        return None

    # Load the JSON data from the script tag
    try:
        json_data = json.loads(script_tag.string)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON on page {page_number} for website {website}: {e}")
        log_error(url, 'JSON Decode Error', response.text)  # Log JSON parse error
        return None

    # Extract reviews from the JSON data
    reviews = []
    if '@graph' in json_data:
        for item in json_data['@graph']:
            if item['@type'] == 'Review':
                profile_link = item['author'].get('url')
                country = None
                if profile_link:
                    # Scrape the user's country from their profile page
                    country = scrape_user_country(profile_link)

                review = {
                    'username': item['author']['name'],
                    'date': item['datePublished'],
                    'comment': item['reviewBody'],
                    'rating': item['reviewRating']['ratingValue'] if 'reviewRating' in item else None,
                    'profile_link': profile_link,
                    'country': country
                }
                reviews.append(review)
    
    return reviews

# Function to scrape multiple pages in parallel with safe IP rotation
def scrape_trustpilot_parallel(output_file, website, max_pages=10, num_threads=5, use_tor=False):
    # Setup Tor if needed
    controller = None
    if use_tor:
        controller = Controller.from_port(port=9051)
        connectTor()  # Establish Tor proxy connection
        try:
            controller.authenticate("abc123")  # or use cookie-based if needed
        except Exception as e:
            print(f"Error authenticating to Tor control port: {e}")
            return

    # Open the CSV file for writing
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['username', 'date', 'comment', 'rating', 'profile_link', 'country']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Prepare page numbers
        page_numbers = list(range(1, max_pages + 1))

        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit page scraping tasks
            futures = {executor.submit(scrape_page, page, website): page for page in page_numbers}

            # Use tqdm to display progress
            for i, future in enumerate(tqdm(as_completed(futures), total=max_pages, desc=f"Scraping {website}")):
                page_number = futures[future]
                try:
                    reviews = future.result()
                    if reviews is None:
                        continue

                    # Write reviews to CSV
                    for review in reviews:
                        writer.writerow(review)

                    # Renew Tor IP after every 10 pages (or change as needed)
                    if use_tor and (i + 1) % 10 == 0:
                        renewTor(controller)
                        showIP()  # Show the renewed IP for debugging
                        time.sleep(random.uniform(2, 5))  # Sleep to prevent being blocked

                except Exception as e:
                    print(f"Error processing page {page_number} for website {website}: {e}")
                    log_error(f"Error on page {page_number}", 'Exception', str(e))  # Log exception errors

            # Sleep between requests to avoid getting blocked
            time.sleep(random.uniform(2, 5))

# Main function to handle command-line arguments
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Trustpilot scraper with IP rotation.')
    parser.add_argument('--website', type=str, required=True, help='The website name to scrape (e.g., trustpilot.com).')
    parser.add_argument('--tor', action='store_true', help='Use Tor for IP rotation.')
    parser.add_argument('--pages', type=int, default=50, help='The number of pages to scrape. Default is 50.')

    args = parser.parse_args()

    output_file = f'{args.website}_reviews.csv'
    scrape_trustpilot_parallel(output_file, args.website, max_pages=args.pages, num_threads=5, use_tor=args.tor)

if __name__ == "__main__":
    main()