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

# --- Caching Configuration ---
CACHE = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION_SECONDS = 600  # Cache for 10 minutes

def get_basic_submission_data(submission_summary):
    """
    Extracts basic person details from the expanded 'person' field in the submission.
    """
    try:
        person_data = submission_summary.get("person", {})
        if not person_data:
            return None

        name_parts = []
        if person_data.get("given_name"):
            name_parts.append(person_data["given_name"])
        if person_data.get("family_name"):
            name_parts.append(person_data["family_name"])
        full_name = " ".join(name_parts) if name_parts else "Anonymous"

        location_parts = []
        addresses = person_data.get("postal_addresses", [])
        if addresses:
            addr = addresses[0]
            if addr.get("locality"):
                location_parts.append(addr["locality"])
            if addr.get("region"):
                location_parts.append(addr["region"])
        location = ", ".join(location_parts)

        return {
            "name": full_name,
            "email": person_data.get("email_addresses", [{}])[0].get("address", ""),
            "location": location,
            "title": person_data.get("custom_fields", {}).get("Title", ""),
            "organization": person_data.get("custom_fields", {}).get("Professional_Affiliation", "")
        }
    except Exception as e:
        print(f"Error extracting submission: {e}")
        return None

def fetch_petition_signatures():
    """
    Fetches all petition signatures using 'expand=person' to reduce API calls.
    """
    print("Fetching petition signatures with expanded person data...")
    all_signatures = []
    next_page_url = f"{AN_BASE_URL}forms/{AN_FORM_ID}/submissions/"

    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=AN_HEADERS, params={"expand": "person"}, timeout=30)
            response.raise_for_status()
            data = response.json()

            submissions_on_page = data.get("_embedded", {}).get("osdi:submissions", [])
            print(f"Fetched {len(submissions_on_page)} submissions")

            for i, submission in enumerate(submissions_on_page):
                signature_data = get_basic_submission_data(submission)
                if signature_data:
                    all_signatures.append(signature_data)

            next_page_url = data.get("_links", {}).get("next", {}).get("href")
            time.sleep(1)  # Be polite to the API

        except Exception as e:
            print(f"Error during fetch: {e}")
            break

    print(f"Finished. Total collected signatures: {len(all_signatures)}")
    return all_signatures

def export_for_squarespace(signatures, format_type="simple"):
    if format_type == "simple":
        return "\n".join([s["name"] for s in signatures if s["name"] != "Anonymous"])
    elif format_type == "detailed":
        output = []
        for s in signatures:
            if s["name"] == "Anonymous":
                continue
            line = s["name"]
            if s["title"]:
                line += f", {s['title']}"
            if s["organization"]:
                line += f", {s['organization']}"
            if s["location"]:
                line += f" ({s['location']})"
            output.append(line)
        return "\n".join(output)
    elif format_type == "json":
        return json.dumps(signatures, indent=2)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        is_cache_valid = (time.time() - CACHE["timestamp"] < CACHE_DURATION_SECONDS)

        if CACHE["data"] and is_cache_valid:
            print("Serving from cache.")
            signatures = CACHE["data"]
        else:
            print("Cache expired or empty. Fetching new data.")
            signatures = fetch_petition_signatures()
            if signatures:
                CACHE["data"] = signatures
                CACHE["timestamp"] = time.time()

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(signatures, indent=2).encode('utf-8'))

if __name__ == "__main__":
    PORT = 8000
    print(f"Server running at http://localhost:{PORT}")
    try:
        httpd = HTTPServer(("localhost", PORT), handler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
