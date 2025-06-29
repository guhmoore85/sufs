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
            if "_embedded" in data and "osdi:tags" in data["_embedded"]:
                for tag in data["_embedded"]["osdi:tags"]:
                    if "name" in tag:
                        tags.append(tag["name"])
            next_page = data.get("_links", {}).get("next", {}).get("href")
        except requests.exceptions.RequestException:
            next_page = None
    return tags

def get_person_details(person_url):
    """Fetches details and tags for a specific person from Action Network."""
    try:
        response = requests.get(person_url, headers=AN_HEADERS)
        response.raise_for_status()
        person_data = response.json()
        taggings_link = person_data.get("_links", {}).get("osdi:taggings", {}).get("href")
        if taggings_link:
            person_data['tags'] = get_person_tags(taggings_link)
        else:
            person_data['tags'] = []
        return person_data
    except requests.exceptions.RequestException:
        return None

def fetch_all_submissions():
    """
    Fetches all submissions, then merges person data and custom fields for each.
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
                for submission in submissions_on_page:
                    # Start by getting the person's core data (name, email, tags)
                    person_url = submission.get("_links", {}).get("osdi:person", {}).get("href")
                    if not person_url:
                        continue
                    
                    person_details = get_person_details(person_url)
                    if not person_details:
                        continue
                        
                    # Now, merge the custom fields from the submission record into the person details
                    # This ensures we have both sets of data.
                    if 'custom_fields' in submission:
                        # If the person object doesn't already have custom_fields, create it
                        if 'custom_fields' not in person_details:
                            person_details['custom_fields'] = {}
                        # Merge the submission's custom fields. This will overwrite any person-level
                        # custom fields if they have the same name, which is usually the desired behavior.
                        person_details['custom_fields'].update(submission['custom_fields'])

                    all_final_details.append(person_details)
                    time.sleep(0.25)
            
            next_page_url = data.get("_links", {}).get("next", {}).get("href")
            if next_page_url:
                time.sleep(0.25)
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            next_page_url = None

    return all_final_details

class handler(BaseHTTPRequestHandler):
    """
    Handles incoming HTTP requests for the Vercel serverless function.
    """
    def do_GET(self):
        submissions_data = fetch_all_submissions()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(submissions_data).encode('utf-8'))
        return
