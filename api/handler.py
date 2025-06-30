from http.server import BaseHTTPRequestHandler
import requests
import json
import time
import os

# --- Configuration ---
AN_API_TOKEN = os.environ.get("AN_API_TOKEN", "165b1a8c3190bce3ba263930dfc034d7")
AN_FORM_ID = os.environ.get("AN_FORM_ID", "3b5f9f80-b7c7-4331-a052-41582c390dac")
AN_BASE_URL = "https://actionnetwork.org/api/v2/"
AN_HEADERS = {
    "OSDI-API-Token": AN_API_TOKEN,
    "Accept": "application/json"
}

# --- Caching ---
# Simple in-memory cache to store the data and reduce API calls.
# The cache will hold the data and a timestamp of when it was fetched.
CACHE = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION_SECONDS = 600  # Cache data for 10 minutes (10 * 60)

def get_full_submission_details(submission_summary):
    """
    Fetches the full details for an individual submission and its associated person,
    then merges them.
    """
    submission_url = submission_summary.get("_links", {}).get("self", {}).get("href")
    if not submission_url:
        return None

    try:
        response = requests.get(submission_url, headers=AN_HEADERS)
        response.raise_for_status()
        full_submission_data = response.json()
        submission_custom_fields = full_submission_data.get('custom_fields', {})

        person_url = full_submission_data.get("_links", {}).get("osdi:person", {}).get("href")
        if not person_url:
            return None

        person_response = requests.get(f"{person_url}?expand=tags", headers=AN_HEADERS)
        person_response.raise_for_status()
        person_details = person_response.json()

        tags = []
        if "_embedded" in person_details and "osdi:tags" in person_details["_embedded"]:
            for tag in person_details["_embedded"]["osdi:tags"]:
                if "name" in tag:
                    tags.append(tag["name"])
        person_details['tags'] = tags

        if 'custom_fields' not in person_details:
            person_details['custom_fields'] = {}
        person_details['custom_fields'].update(submission_custom_fields)
        
        return person_details
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def fetch_all_submissions():
    """
    Fetches all submission summaries and then gets the full merged details for each.
    """
    all_final_details = []
    next_page_url = f"{AN_BASE_URL}forms/{AN_FORM_ID}/submissions/"

    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=AN_HEADERS)
            response.raise_for_status()
            data = response.json()

            if "_embedded" in data and "osdi:submissions" in data["_embedded"]:
                submissions_on_page = data["_embedded"]["osdi:submissions"]
                for submission_summary in submissions_on_page:
                    full_details = get_full_submission_details(submission_summary)
                    if full_details:
                        all_final_details.append(full_details)
                    time.sleep(0.3)
            
            next_page_url = data.get("_links", {}).get("next", {}).get("href")
            if next_page_url:
                time.sleep(0.3)
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            next_page_url = None

    return all_final_details

class handler(BaseHTTPRequestHandler):
    """
    Handles incoming HTTP requests for the Vercel serverless function.
    """
    def do_GET(self):
        # Check if the cache is valid
        is_cache_valid = (time.time() - CACHE["timestamp"]) < CACHE_DURATION_SECONDS
        
        if CACHE["data"] and is_cache_valid:
            # Serve data from the cache
            print("Serving data from cache.")
            submissions_data = CACHE["data"]
        else:
            # Fetch fresh data from the API
            print("Cache expired or empty. Fetching fresh data from API.")
            submissions_data = fetch_all_submissions()
            
            # Update the cache
            if submissions_data: # Only cache if data was successfully fetched
                CACHE["data"] = submissions_data
                CACHE["timestamp"] = time.time()
                print(f"Cache updated at {CACHE['timestamp']}")

        # Set the response headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Send the data back as a JSON response
        self.wfile.write(json.dumps(submissions_data).encode('utf-8'))
        return
