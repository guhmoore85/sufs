from http.server import BaseHTTPRequestHandler
import requests
import json
import time
import os

# --- Configuration ---
# It's best practice to set these as Environment Variables in your Vercel project settings.
# This keeps your secret keys out of the code.
AN_API_TOKEN = os.environ.get("AN_API_TOKEN", "165b1a8c3190bce3ba263930dfc034d7")
AN_FORM_ID = os.environ.get("AN_FORM_ID", "3b5f9f80-b7c7-4331-a052-41582c390dac")

AN_BASE_URL = "https://actionnetwork.org/api/v2/"
AN_HEADERS = {
    "OSDI-API-Token": AN_API_TOKEN,
    "Accept": "application/json"
}

def get_person_tags(taggings_url):
    """Fetches all tags for a specific person, handling pagination."""
    tags = []
    next_page = taggings_url
    while next_page:
        try:
            response = requests.get(next_page, headers=AN_HEADERS)
            response.raise_for_status()
            data = response.json()
            # Extract tag names from the embedded tag objects
            if "_embedded" in data and "osdi:tags" in data["_embedded"]:
                for tag in data["_embedded"]["osdi:tags"]:
                    if "name" in tag:
                        tags.append(tag["name"])
            # Check for a next page
            next_page = data.get("_links", {}).get("next", {}).get("href")
        except requests.exceptions.RequestException:
            # On error, stop trying to fetch tags for this person
            next_page = None
    return tags


def get_person_details(person_url):
    """Fetches details and tags for a specific person from Action Network."""
    try:
        response = requests.get(person_url, headers=AN_HEADERS)
        response.raise_for_status()
        person_data = response.json()

        # After getting person data, fetch their tags
        taggings_link = person_data.get("_links", {}).get("osdi:taggings", {}).get("href")
        if taggings_link:
            person_data['tags'] = get_person_tags(taggings_link)
        else:
            person_data['tags'] = []
            
        return person_data
        
    except requests.exceptions.RequestException:
        return None # Return None on failure

def fetch_all_submissions():
    """Fetches all pages of submissions and their corresponding person details."""
    all_person_details = []
    next_page_url = f"{AN_BASE_URL}forms/{AN_FORM_ID}/submissions/"

    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=AN_HEADERS)
            response.raise_for_status()
            data = response.json()

            if "_embedded" in data and "osdi:submissions" in data["_embedded"]:
                submissions_on_page = data["_embedded"]["osdi:submissions"]
                for submission in submissions_on_page:
                    if "osdi:person" in submission["_links"]:
                        person_url = submission["_links"]["osdi:person"]["href"]
                        person_data = get_person_details(person_url)
                        if person_data:
                            all_person_details.append(person_data)
                        # Be polite to the API, but slightly faster
                        time.sleep(0.25)
            
            next_page_url = data.get("_links", {}).get("next", {}).get("href")
            if next_page_url:
                time.sleep(0.25)
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            next_page_url = None # Stop on any error

    return all_person_details

class handler(BaseHTTPRequestHandler):
    """
    Handles incoming HTTP requests for the Vercel serverless function.
    """
    def do_GET(self):
        # Fetch the data from Action Network
        submissions_data = fetch_all_submissions()

        # Set the response headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Allows any site to access
        self.end_headers()

        # Send the data back as a JSON response
        self.wfile.write(json.dumps(submissions_data).encode('utf-8'))
        return

