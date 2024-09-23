# Use the official Python image as the base
FROM python:3.10-slim

# Install Tor, Git, and ss (part of iproute2)
RUN apt-get update && apt-get install -y tor git iproute2

# Set the working directory to /app
WORKDIR /app

# Clone the GitHub repository into /app
RUN git clone https://github.com/AthomsG/scraping_with_tor .

# Set the working directory to the location of scraper.py
WORKDIR /app/scrape_reviews_website

# Install Python dependencies from the requirements.txt file in the root folder
RUN pip install --no-cache-dir -r /app/requirements.txt

# Expose Tor's ports
EXPOSE 9050 9051

# Tor Configuration: Modify the torrc file and add hashed password
RUN echo "Automating torrc modifications..." \
    && sed -i 's/#ControlPort 9051/ControlPort 9051/' /etc/tor/torrc \
    && sed -i 's/#CookieAuthentication 1/CookieAuthentication 1/' /etc/tor/torrc \
    && TOR_PASSWORD="abc123" \
    && HASHED_PASSWORD=$(tor --hash-password "$TOR_PASSWORD" | tail -n 1) \
    && echo "HashedControlPassword $HASHED_PASSWORD" >> /etc/tor/torrc \
    && echo "Tor configuration updated."

# Create the scrape command
RUN echo '#!/bin/bash\n\
OUTPUT_DIR="/app/output"\n\
python scraper.py "$@"\n\
if [ $? -eq 0 ]; then\n\
    echo "Scraper ran successfully!"\n\
    if [ ! -d "$OUTPUT_DIR" ]; then\n\
        mkdir -p "$OUTPUT_DIR"\n\
    fi\n\
    mv *.csv "$OUTPUT_DIR"\n\
    echo "CSV files have been moved to $OUTPUT_DIR"\n\
else\n\
    echo "Scraper failed!"\n\
    exit 1\n\
fi' > /usr/local/bin/scrape && chmod +x /usr/local/bin/scrape

# Start Tor, wait for it to be ready, and open the shell
ENTRYPOINT service tor start && echo "Waiting for Tor to be ready..." && \
    while ! ss -tuln | grep -q ':9051'; do echo "Waiting..."; sleep 1; done && \
    echo "Tor is ready!" && /bin/bash
