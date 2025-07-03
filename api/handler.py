import requests
import json
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Configuration ---
AN_API_TOKEN = os.environ.get("AN_API_TOKEN", "165b1a8c3190bce3ba263930dfc034d7")
AN_FORM_ID = os.environ.get("AN_FORM_ID", "3b5f9f80-b7c7-4331-a052-41582c390dac")
AN_BASE_URL = "https://actionnetwork.org/api/v2/"
AN_HEADERS = {
    "OSDI-API-Token": AN_API_TOKEN,
    "Accept": "application/json"
}

# --- Cache Configuration ---
CACHE_FILE = "signatures_cache.json"
CACHE_DURATION_SECONDS = 3600  # Cache for 1 hour

def get_person_data(person_url):
    """
    Fetches full person data from the API with a retry mechanism.
    """
    max_retries = 5
    backoff_factor = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(person_url, headers=AN_HEADERS, timeout=30)
            # Raise an exception for 4xx/5xx responses
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # For 429 or 5xx errors, wait and retry
            if e.response is not None and (e.response.status_code == 429 or e.response.status_code >= 500):
                wait_time = backoff_factor ** attempt
                print(f"Request for {person_url} failed with status {e.response.status_code}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Error processing submission URL {person_url}: {e}")
                return None # For non-retriable errors, stop trying
    print(f"Failed to fetch person data from {person_url} after {max_retries} attempts.")
    return None

def fetch_petition_signatures():
    """
    Fetches all petition signatures with robust error handling, rate limiting, and retries.
    """
    print("Starting to fetch all petition signatures...")
    all_signatures = []
    next_page_url = f"{AN_BASE_URL}forms/{AN_FORM_ID}/submissions/"
    page_count = 0
    max_retries = 5 # Retries for fetching pages of submissions
    backoff_factor = 2 # Exponential backoff factor

    # Loop through all pages of submissions
    while next_page_url:
        page_fetched = False
        for attempt in range(max_retries):
            try:
                print(f"Fetching page {page_count + 1}...")
                response = requests.get(next_page_url, headers=AN_HEADERS, timeout=30)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()
                page_fetched = True
                break # Success, exit retry loop
            except requests.exceptions.Timeout:
                print("Request timed out. Retrying...")
                time.sleep(backoff_factor ** attempt)
            except requests.exceptions.HTTPError as e:
                # Specifically handle 429 (Too Many Requests) and 504 (Gateway Timeout)
                if e.response.status_code == 429 or e.response.status_code == 504:
                    wait_time = backoff_factor ** attempt
                    print(f"Request failed with status {e.response.status_code}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"An unexpected HTTP error occurred: {e}")
                    next_page_url = None # Stop pagination on critical error
                    break
            except requests.exceptions.RequestException as e:
                print(f"A request error occurred: {e}")
                next_page_url = None # Stop pagination
                break

        if not page_fetched:
            print(f"Failed to fetch page {page_count + 1} after {max_retries} attempts. Stopping.")
            break

        if "_embedded" in data and "osdi:submissions" in data["_embedded"]:
            submissions_on_page = data["_embedded"]["osdi:submissions"]
            print(f"Found {len(submissions_on_page)} submissions on this page.")

            for i, submission in enumerate(submissions_on_page):
                person_url = submission.get("_links", {}).get("osdi:person", {}).get("href")
                if person_url:
                    signature_data = get_person_data(person_url)
                    if signature_data:
                        all_signatures.append(signature_data)

                # Gentle rate limiting to avoid hitting the API too hard
                if (i + 1) % 10 == 0:
                    time.sleep(0.5)

        # Get the URL for the next page
        links = data.get("_links", {})
        next_page_url = links.get("next", {}).get("href") if links else None
        page_count += 1

        if next_page_url:
            time.sleep(1)  # Pause between fetching pages

    print(f"Fetched {len(all_signatures)} total signatures from {page_count} pages.")
    return all_signatures

class handler(BaseHTTPRequestHandler):
    """
    HTTP request handler that serves petition data with file-based caching.
    """
    def do_GET(self):
        signatures_data = None
        cache_is_valid = False

        # Check if cache file exists and is recent
        if os.path.exists(CACHE_FILE):
            file_mod_time = os.path.getmtime(CACHE_FILE)
            if (time.time() - file_mod_time) < CACHE_DURATION_SECONDS:
                cache_is_valid = True

        if cache_is_valid:
            print("Serving data from valid cache file.")
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    signatures_data = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error reading cache file: {e}. Fetching fresh data.")
                # Invalidate cache if it's corrupted
                cache_is_valid = False

        if not signatures_data:
            print("Cache is empty or expired. Fetching fresh data from API.")
            signatures_data = fetch_petition_signatures()

            # If data was fetched successfully, update the cache file
            if signatures_data:
                try:
                    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(signatures_data, f, indent=2)
                    print(f"Cache file '{CACHE_FILE}' has been updated.")
                except IOError as e:
                    print(f"Error writing to cache file: {e}")

        # Ensure we have some data to return
        if signatures_data is None:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = json.dumps({"error": "Failed to retrieve signature data."})
            self.wfile.write(error_response.encode('utf-8'))
            return

        # Prepare and send the successful JSON response
        json_response = json.dumps(signatures_data, indent=2)
        print(f"Successfully prepared response with {len(signatures_data)} signatures.")

        # Set response headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Send JSON response
        self.wfile.write(json_response.encode('utf-8'))


# Main execution block for local testing
if __name__ == "__main__":
    PORT = 8000
    print(f"Starting local server at http://localhost:{PORT}")
    print(f"Data will be cached in '{CACHE_FILE}' for {CACHE_DURATION_SECONDS // 60} minutes.")

    try:
        httpd = HTTPServer(("localhost", PORT), handler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
