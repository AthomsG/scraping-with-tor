import requests
import json
import csv
import time
import random
import logging
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    filename='scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Locks for thread synchronization
tor_lock = Lock()
counter_lock = Lock()

# Shared variable to track 403 errors across requests
shared_403_counter = 0
shared_403_threshold = 3  # Number of 403 errors to trigger IP renewal

# Function to create a Tor session without global socket patching
def get_tor_session():
    session = requests.Session()
    session.proxies = {
        'http': 'socks5h://127.0.0.1:9050',  # Use Tor SOCKS proxy
        'https': 'socks5h://127.0.0.1:9050'
    }
    return session

# Function to renew Tor IP with a delay to avoid rate-limiting
def renewTor(controller, session, min_wait=10, max_wait=15):
    global shared_403_counter
    old_ip = get_current_ip(session)
    try:
        with tor_lock:
            logging.info("Initiating Tor identity change...")
            controller.authenticate("abc123")
            controller.signal(Signal.NEWNYM)
            time.sleep(random.uniform(min_wait, max_wait))  # Wait for Tor to get a new identity
            session = get_tor_session()  # Create a new session with the new IP
            new_ip = get_current_ip(session)
            logging.info(f"Tor identity changed. Old IP: {old_ip}, New IP: {new_ip}")
            shared_403_counter = 0  # Reset the 403 counter after IP renewal
    except Exception as e:
        logging.error(f"Error renewing TOR IP: {e}")
    return session  # Return the new session

# Function to get current IP
def get_current_ip(session):
    try:
        ip = session.get('https://icanhazip.com').text.strip()
        return ip
    except Exception as e:
        logging.error(f"Error retrieving IP: {e}")
        return None

# Function to print current IP to terminal
def showIP(session):
    try:
        ip = get_current_ip(session)
        print(f"Current IP: {ip}")
        logging.info(f"Current IP: {ip}")
    except Exception as e:
        logging.error(f"Error retrieving IP: {e}")

# Function to update headers dynamically
def update_headers(website=None):
    referers = ["https://www.google.com", "https://www.trustpilot.com", "https://www.duckduckgo.com"]
    if website:
        referers.append(f'https://www.trustpilot.com/review/{website}')
    headers = {
        'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; '
                      f'{random.choice(["AppleWebKit/537.36", "Gecko/20100101"])} '
                      f'Chrome/91.0.{random.randint(1000, 5000)}.124 Safari/537.36',
        'Accept-Language': 'de,en;q=0.9',
        'Referer': random.choice(referers),  # Randomize referer
    }
    return headers

# Function to retry the request and handle 403/429 and 500 errors
def fetch_with_retry(session, url, headers, controller, retries=1):
    global shared_403_counter
    for attempt in range(retries + 1):
        response = session.get(url, headers=headers)
        if response.status_code == 500:  # Server internal error, wait and retry
            logging.error(f"Error {response.status_code} on {url}, retrying after delay...")
            time.sleep(random.uniform(5, 10))  # Wait before retrying for server errors
        elif response.status_code in [403, 429]:  # Blocked by server
            logging.error(f"Error {response.status_code} on {url}, incrementing 403 counter...")
            with counter_lock:
                shared_403_counter += 1
                if shared_403_counter >= shared_403_threshold:
                    logging.info(f"Reached 403 error threshold ({shared_403_counter}). Renewing Tor IP and retrying...")
                    session = renewTor(controller, session)
                    headers = update_headers()
            time.sleep(5)  # Wait before retrying
        else:
            # Only log if we successfully retried after an error
            if attempt > 0 and response.status_code == 200:
                logging.info(f"Request successful on retry after {attempt} attempts.")
            return response
    return response  # Return response after retries

# Function to scrape the user's country from their profile page
def scrape_user_country(profile_link, controller, use_tor):
    headers = update_headers()  # Get fresh headers
    if use_tor:
        session = get_tor_session()
    else:
        session = requests.Session()
    response = fetch_with_retry(session, profile_link, headers, controller)
    if response and response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        country_tag = soup.find('p', attrs={'data-consumer-country-typography': 'true'})
        if country_tag:
            return country_tag.text.strip()
        else:
            logging.info(f"Country not found for user profile: {profile_link}")
            return None
    else:
        logging.error(f"Failed to retrieve profile page: {profile_link}. Error: {response.status_code}")
        return response.status_code  # Return the error code for early IP renewal logic

# Function to scrape a single page of reviews (Stage 1)
def scrape_page(page_number, website, controller, use_tor, starting_date=None):
    if use_tor:
        session = get_tor_session()
    else:
        session = requests.Session()
    url = f'https://www.trustpilot.com/review/{website}?page={page_number}'
    headers = update_headers(website)  # Get fresh headers for each request
    response = fetch_with_retry(session, url, headers, controller)
    if response.status_code == 404:
        logging.info(f"Page {page_number} not found (404).")
        return None, False
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')
        if not script_tag:
            logging.info(f"No JSON-LD script tag found on page {page_number} for website {website}")
            return None, False
        try:
            json_data = json.loads(script_tag.string)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON on page {page_number} for website {website}: {e}")
            return None, False
        reviews = []
        stop_scraping = False
        if '@graph' in json_data:
            for item in json_data['@graph']:
                if item['@type'] == 'Review':
                    review_date = item['datePublished']
                    # Remove milliseconds if present before parsing the date
                    review_date = review_date.split('.')[0] + 'Z'
                    review_date_dt = datetime.strptime(review_date, '%Y-%m-%dT%H:%M:%SZ')


                    if starting_date and review_date_dt < starting_date:
                        stop_scraping = True  # Set flag to stop scraping further pages
                        break

                    profile_link = item['author'].get('url')
                    review = {
                        'username': item['author']['name'],
                        'date': review_date,
                        'comment': item['reviewBody'],
                        'rating': item['reviewRating']['ratingValue'] if 'reviewRating' in item else None,
                        'profile_link': profile_link
                    }
                    reviews.append(review)
        return reviews, stop_scraping
    else:
        logging.error(f"Failed to retrieve page {page_number} for website {website}. Error: {response.status_code}")
        return response.status_code, False

# Function to fetch user countries (Stage 2)
def fetch_country_for_review(review, controller, use_tor):
    profile_link = review.get('profile_link')
    if profile_link:
        country = scrape_user_country(profile_link, controller, use_tor)
        review['country'] = country
    else:
        review['country'] = None

# Function to scrape multiple pages in parallel with safe IP rotation
def scrape_trustpilot_parallel(output_file, website, max_pages=10, num_threads=5, use_tor=False, get_countries=False, starting_date=None):
    # Setup Tor if needed
    controller = None
    if use_tor:
        controller = Controller.from_port(port=9051)
        try:
            controller.authenticate("abc123")
        except Exception as e:
            logging.error(f"Error authenticating to Tor control port: {e}")
            return
    reviews = []  # Collect all reviews here
    stop_scraping = False
    page_numbers = list(range(1, max_pages + 1))

    with tqdm(total=max_pages, desc="Scraping pages") as progress_bar:
        for page in page_numbers:
            if stop_scraping:
                break  # Stop scraping if the date condition is met
            result, stop_scraping = scrape_page(page, website, controller, use_tor, starting_date)
            if result:
                reviews.extend(result)
            progress_bar.update(1)

    # Stage 2: Fetch user countries if requested
    if get_countries:
        with tqdm(total=len(reviews), desc="Fetching countries") as progress_bar:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = {executor.submit(fetch_country_for_review, review, controller, use_tor): review for review in reviews}
                for future in as_completed(futures):
                    progress_bar.update(1)

    # Write all reviews to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['username', 'date', 'comment', 'rating', 'profile_link']
        if get_countries:
            fieldnames.append('country')
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for review in reviews:
            writer.writerow(review)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Trustpilot scraper with IP rotation.')
    parser.add_argument('--website', type=str, required=True, help='The website name to scrape (e.g., example.com).')
    parser.add_argument('--tor', action='store_true', help='Use Tor for IP rotation.')
    parser.add_argument('--pages', type=int, default=50, help='The number of pages to scrape. Default is 50.')
    parser.add_argument('--get_countries', action='store_true', help='Include to fetch user countries.')
    parser.add_argument('--starting_date', type=str, help='Stop scraping when reviews older than this date are found (format: YYYY-MM-DD).')
    args = parser.parse_args()

    # Convert starting_date to datetime object if provided
    starting_date = None
    if args.starting_date:
        starting_date = datetime.strptime(args.starting_date, '%Y-%m-%d')

    output_file = f'{args.website}_reviews.csv'
    scrape_trustpilot_parallel(
        output_file,
        args.website,
        max_pages=args.pages,
        num_threads=5,
        use_tor=args.tor,
        get_countries=args.get_countries,
        starting_date=starting_date
    )

if __name__ == "__main__":
    main()
