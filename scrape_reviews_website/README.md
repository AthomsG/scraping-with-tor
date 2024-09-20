    # Trustpilot Scraper with Tor-based IP Rotation

    This is a web scraper built for extracting reviews from websites like Trustpilot. The scraper utilizes `requests` to retrieve pages and BeautifulSoup to parse the content. To avoid getting rate-limited, the scraper is designed to work with Tor to rotate IP addresses after every 10 pages. This allows for anonymous browsing and bypasses rate limiting or blocks that could be imposed by the website being scraped.

    ## Features
    - Scrapes review pages in parallel using multiple threads to speed up the process.
    - Uses Tor to rotate IP addresses after every 10 pages, preventing rate limiting and increasing anonymity.
    - Logs any errors (such as HTTP 500 or 404 errors) along with the response content to a file for later review (`scraper_errors.log`).
    - Supports command-line arguments to specify the website, number of pages to scrape, and whether to use Tor.

    Additionally, you need to have Tor installed and running on your system. Tor must be configured to listen on ports `9050` (for SOCKS5 proxy) and `9051` (for the control port used to rotate IP addresses).

    ## Usage

    Here is an example command for scraping reviews from the website `www.ups.com`, scraping 50 pages with IP rotation via Tor:

    ```bash
    python trust_pilot_scraper.py --website www.ups.com --tor --pages 50
    ```

    ### Command-line Arguments
    - `--website`: The website from which you want to scrape reviews.
    - `--tor`: Use this flag to enable Tor for IP rotation.
    - `--pages`: Specify the number of pages to scrape. The default is 50 pages.

    ## Logging
    Any failed requests, such as HTTP 500 or 404 errors, will be logged to the `scraper_errors.log` file, along with the response content for debugging purposes.
