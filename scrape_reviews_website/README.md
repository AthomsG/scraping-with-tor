# Trustpilot Scraper with Tor-based IP Rotation

This scraper extracts reviews from Trustpilot using multithreading and Tor for IP rotation. It's designed to bypass rate limits and blocks by rotating IP addresses when necessary.

## Features

- **Parallel Scraping with Threads**: Utilizes `ThreadPoolExecutor` to scrape multiple pages concurrently, increasing efficiency.
- **Tor Integration for IP Rotation**: Uses the Tor network to rotate IP addresses after encountering a threshold of HTTP 403 errors, enhancing anonymity and avoiding rate limits.
- **Dynamic Headers**: Randomizes user agents and referers to mimic real browser behavior and reduce detection.
- **Two-Stage Pipeline**:
  - **Stage 1**: Collects reviews without fetching user countries.
  - **Stage 2**: Optionally fetches user countries when the `--get_countries` flag is used.
- **Error Handling and Logging**: Implements robust error handling with retries and logs important events and errors to `scraper.log`.
- **Command-Line Interface**: Allows customization of scraping parameters via command-line arguments.

## Usage

Example command to scrape reviews from www.ups.com, scraping 50 pages with Tor and fetching user countries:

```bash
python trust_pilot_scraper.py --website www.ups.com --tor --pages 50 --get_countries
```

## Command-Line Arguments

- `--website`: **(Required)** The website from which to scrape reviews (e.g., www.ups.com).
- `--tor`: Enable Tor for IP rotation.
- `--pages`: Number of pages to scrape (default is 50).
- `--get_countries`: Fetch user countries by visiting profile pages.
- `--help`: Display help message with all options.

## How It Works

### Multithreading with `ThreadPoolExecutor`
- **Concurrency**: Scrapes multiple pages and fetches user countries in parallel using threads.
- **Performance**: Increases scraping speed by utilizing multiple threads (`num_threads` parameter).

### Tor for IP Rotation
- **Anonymity**: Routes HTTP requests through the Tor network using SOCKS5 proxies.
- **IP Rotation**: Changes IP address when a threshold of HTTP 403 errors is reached to avoid bans.
- **Synchronization**: Uses threading locks to ensure only one thread changes the Tor identity at a time.

### Dynamic Request Headers
- **User Agents and Referers**: Randomly selects user agents and referers to simulate real user behavior.
- **Anti-Bot Measures**: Helps in bypassing simple bot detection mechanisms.

### Two-Stage Pipeline

1. **Stage 1 - Scrape Reviews**:
   - Collects reviews from the specified number of pages.
   - Extracts username, date, comment, rating, and profile link.

2. **Stage 2 - Fetch User Countries (optional)**:
   - If `--get_countries` is specified, visits each user's profile page to extract their country.
   - This stage can be time-consuming due to additional requests.

### Error Handling and Logging
- **Retries**: Implements retries for HTTP 500, 403, and 429 errors with exponential backoff.
- **Logging**: Records significant events, errors, and IP changes to `scraper.log` for debugging and monitoring.
- **Thresholds**: Uses a shared counter with thread-safe locks to trigger IP rotation after a set number of 403 errors.

## Notes

- **Tor Authentication**: Ensure Tor control port authentication is set correctly. Replace "abc123" in the script with your Tor control port password if required.
- **Adjustable Parameters**: You can modify thresholds, delays, and the number of threads to optimize performance based on your environment.
- **Legal Considerations**: Be mindful of the website's terms of service and legal implications of scraping.

## Summary of Techniques Used

- **Multithreading**: Enhances performance by parallelizing network I/O-bound tasks.
- **Tor Integration**: Provides anonymity and IP rotation capabilities to avoid rate limiting.
- **Thread Synchronization**: Ensures thread-safe operations when accessing shared resources like counters and Tor identity changes.
- **Dynamic Headers and Randomization**: Mimics human behavior to reduce detection by anti-bot systems.
- **Error Handling and Retries**: Robust handling of network errors and server responses to maintain stability.
