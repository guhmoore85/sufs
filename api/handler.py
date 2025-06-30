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

def get_person_details_and_tags(person_url):
    """
    Fetches core person details and explicitly fetches all associated tags
    by following the 'osdi:taggings' link.
    """
    try:
        # First, get the main person object
        person_response = requests.get(person_url, headers=AN_HEADERS)
        person_response.raise_for_status()
        person_details = person_response.json()

        # Initialize tags as an empty list
        person_details['tags'] = []

        # Find the link to the person's taggings collection
        taggings_link = person_details.get("_links", {}).get("osdi:taggings", {}).get("href")
        
        if taggings_link:
            # Use ?expand=osdi:tag to embed the full tag object in the response,
            # which is more efficient than fetching each tag individually.
            tags_url = f"{taggings_link}?expand=osdi:tag"
            tags_response = requests.get(tags_url, headers=AN_HEADERS)
            tags_response.raise_for_status()
            taggings_data = tags_response.json()

            # Extract the tag names from the embedded tag objects
            tags = []
            if "_embedded" in taggings_data and "osdi:taggings" in taggings_data["_embedded"]:
                for tagging in taggings_data["_embedded"]["osdi:taggings"]:
                    # The tag object is now embedded inside each "tagging"
                    if "_embedded" in tagging and "osdi:tag" in tagging["_embedded"]:
                        tag_name = tagging["_embedded"]["osdi:tag"].get("name")
                        if tag_name:
                            tags.append(tag_name)
            person_details['tags'] = tags
        
        return person_details

    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def get_full_submission_details(submission_summary):
    """
    Fetches the full details for an individual submission and its associated person,
    then merges them.
    """
    # Get the URL for the full submission record
    submission_url = submission_summary.get("_links", {}).get("self", {}).get("href")
    if not submission_url:
        return None

    try:
        # Fetch the full submission record to get its custom fields
        response = requests.get(submission_url, headers=AN_HEADERS)
        response.raise_for_status()
        full_submission_data = response.json()
        submission_custom_fields = full_submission_data.get('custom_fields', {})

        # Get the associated person's details, which now includes fetching their tags
        person_url = full_submission_data.get("_links", {}).get("osdi:person", {}).get("href")
        if not person_url:
            return None # Can't proceed without a person
            
        person_details = get_person_details_and_tags(person_url)

        if not person_details:
             return None

        # Merge the submission's custom fields into the person object
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
                    # Be polite to the API
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
        submissions_data = fetch_all_submissions()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(submissions_data).encode('utf-8'))
        return

