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

# def get_basic_submission_data(submission_summary):
#     """
#     Gets basic submission data without making additional API calls per submission.
#     This is much faster and avoids rate limits.
#     """
#     try:
#         # Try to get person data from the submission summary first
#         person_data = submission_summary.get("person", {})
        
#         if person_data:
#             name_parts = []
#             if person_data.get("given_name"):
#                 name_parts.append(person_data["given_name"])
#             if person_data.get("family_name"):
#                 name_parts.append(person_data["family_name"])
            
#             full_name = " ".join(name_parts) if name_parts else "Anonymous"
            
#             return {
#                 "name": full_name,
#                 "email": person_data.get("email_addresses", [{}])[0].get("address", ""),
#                 "location": "",  
#                 "title": person_data.get("custom_fields", {}).get("Title", ""),
#                 "organization": person_data.get("custom_fields", {}).get("Professional_Affiliation", "")
#             }
        
#         # If no person data in submission, we need to fetch it
#         person_url = submission_summary.get("_links", {}).get("osdi:person", {}).get("href")
#         if person_url:
#             response = requests.get(person_url, headers=AN_HEADERS)
#             response.raise_for_status()
#             person_details = response.json()
            
#             name_parts = []
#             if person_details.get("given_name"):
#                 name_parts.append(person_details["given_name"])
#             if person_details.get("family_name"):
#                 name_parts.append(person_details["family_name"])
            
#             full_name = " ".join(name_parts) if name_parts else "Anonymous"
            
#             # Get location info
#             location_parts = []
#             addresses = person_details.get("postal_addresses", [])
#             if addresses and addresses[0]:
#                 addr = addresses[0]
#                 if addr.get("locality"):
#                     location_parts.append(addr["locality"])
#                 if addr.get("region"):
#                     location_parts.append(addr["region"])
            
#             location = ", ".join(location_parts)
            
#             return {
#                 "name": full_name,
#                 "email": person_details.get("email_addresses", [{}])[0].get("address", ""),
#                 "location": location,
#                 "title": person_details.get("custom_fields", {}).get("Title", ""),
#                 "organization": person_details.get("custom_fields", {}).get("Professional_Affiliation", "")
#             }
        
#         return None
        
#     except Exception as e:
#         print(f"Error processing submission: {e}")
#         return None

def get_basic_submission_data(submission_summary):
    """
    Gets the full person data from the API and returns it complete.
    """
    try:
       
        person_url = submission_summary.get("_links", {}).get("osdi:person", {}).get("href")
        if person_url:
            response = requests.get(person_url, headers=AN_HEADERS)
            response.raise_for_status()
            person_details = response.json()
            
            
            return person_details
        
        return None
        
    except Exception as e:
        print(f"Error processing submission: {e}")
        return None
    
def fetch_petition_signatures():
    """
    Fetches petition signatures with error handling and rate limiting.
    """
    print("Starting to fetch petition signatures...")
    all_signatures = []
    next_page_url = f"{AN_BASE_URL}forms/{AN_FORM_ID}/submissions/"
    page_count = 0
    
    # while next_page_url:  # Get all pages
    while next_page_url and page_count < 20:  # Get the latest 20 pages
        try:
            print(f"Fetching page {page_count + 1}...")
            response = requests.get(next_page_url, headers=AN_HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "_embedded" in data and "osdi:submissions" in data["_embedded"]:
                submissions_on_page = data["_embedded"]["osdi:submissions"]
                print(f"Found {len(submissions_on_page)} submissions on this page")
                
                for i, submission in enumerate(submissions_on_page):
                    signature_data = get_basic_submission_data(submission)
                    if signature_data:
                        all_signatures.append(signature_data)
                    
                    # Rate limiting 
                    if i % 5 == 0:  # Pause every 5 requests 
                        time.sleep(0.3)
            
            # Get next page
            links = data.get("_links", {})
            next_page_url = links.get("next", {}).get("href") if links else None
            page_count += 1
            
            if next_page_url:
                time.sleep(0.5)  # Pause between pages
                
        except requests.exceptions.Timeout:
            print("Request timed out. Retrying...")
            time.sleep(1)
            continue
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
    
    print(f"Fetched {len(all_signatures)} total signatures")
    return all_signatures

def export_for_squarespace(signatures, format_type="simple"):
    """
    Exports the signatures in different formats for Squarespace.
    """
    if format_type == "simple":
        # Just names, one per line
        names = [sig["name"] for sig in signatures if sig["name"] != "Anonymous"]
        return "\n".join(names)
    
    elif format_type == "detailed":
        # Names with titles/organizations
        detailed_list = []
        for sig in signatures:
            if sig["name"] == "Anonymous":
                continue
            
            line = sig["name"]
            if sig["title"] and sig["organization"]:
                line += f", {sig['title']}, {sig['organization']}"
            elif sig["title"]:
                line += f", {sig['title']}"
            elif sig["organization"]:
                line += f", {sig['organization']}"
            
            if sig["location"]:
                line += f" ({sig['location']})"
            
            detailed_list.append(line)
        
        return "\n".join(detailed_list)
    
    elif format_type == "json":
        # Full JSON for custom processing
        return json.dumps(signatures, indent=2)

from http.server import BaseHTTPRequestHandler, HTTPServer

# Add caching 
CACHE = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION_SECONDS = 600  # Cache for 10 minutes

class handler(BaseHTTPRequestHandler):
    """
    HTTP request handler that returns JSON response.
    """
    def do_GET(self):
        # Check if cache is valid
        is_cache_valid = (time.time() - CACHE["timestamp"]) < CACHE_DURATION_SECONDS
        
        if CACHE["data"] and is_cache_valid:
            print("Serving data from cache.")
            signatures_data = CACHE["data"]
        else:
            print("Cache expired or empty. Fetching fresh data from API.")
            signatures_data = fetch_petition_signatures()
            
            # Update cache
            if signatures_data:
                CACHE["data"] = signatures_data
                CACHE["timestamp"] = time.time()
                print(f"Cache updated at {CACHE['timestamp']}")
        
        # Log the JSON result
        json_response = json.dumps(signatures_data, indent=2)
        print(f"\n=== JSON RESPONSE ===")
        print(f"Total signatures: {len(signatures_data)}")
        print("First 2 signatures:")
        print(json.dumps(signatures_data[:2], indent=2))
        print("...\n")
        
        # Set response headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Send JSON response
        self.wfile.write(json_response.encode('utf-8'))

# def main():
#     """
#     Main function to run the petition signature extraction.
#     """
#     # print("=== Petition Signature Extractor ===")
#     # print("This will fetch signatures and format them for Squarespace")
#     # print()
    
#     # Fetch the signatures
#     signatures = fetch_petition_signatures()
    
#     if not signatures:
#         print("No signatures found or API error occurred.")
#         return
    
#     print(f"\n=== RESULTS ===")
#     print(f"Total signatures collected: {len(signatures)}")
    
#     # Exporting in different formats
#     print("\n--- SIMPLE NAMES LIST ---")
#     simple_list = export_for_squarespace(signatures, "simple")
#     print(simple_list[:500] + "..." if len(simple_list) > 500 else simple_list)
    
#     print("\n--- DETAILED LIST ---")
#     detailed_list = export_for_squarespace(signatures, "detailed")
#     print(detailed_list[:500] + "..." if len(detailed_list) > 500 else detailed_list)
    
#     # Log the full JSON result
#     json_result = export_for_squarespace(signatures, "json")
#     print(f"\n--- FULL JSON RESULT (first 1000 chars) ---")
#     print(json_result[:1000] + "..." if len(json_result) > 1000 else json_result)
    
#     # Save to files
#     # with open("petition_signatures_simple.txt", "w", encoding="utf-8") as f:
#     #     f.write(simple_list)
    
#     # with open("petition_signatures_detailed.txt", "w", encoding="utf-8") as f:
#     #     f.write(detailed_list)
    
#     # with open("petition_signatures_full.json", "w", encoding="utf-8") as f:
#     #     f.write(json_result)
    
#     # print(f"\n=== FILES SAVED ===")
#     # print("petition_signatures_simple.txt - Just names for Squarespace")
#     # print("petition_signatures_detailed.txt - Names with titles/orgs")
#     # print("petition_signatures_full.json - Complete data")
#     # print()

# def start_server():
#     """
#     Start the HTTP server to serve JSON responses.
#     """
#     PORT = 8000
#     print(f"\n=== STARTING HTTP SERVER ===")
#     print(f"Server running at http://localhost:{PORT}")
    
#     try:
#         httpd = HTTPServer(("localhost", PORT), handler)
#         httpd.serve_forever()
#     except KeyboardInterrupt:
#         print("\nServer stopped.")

# if __name__ == "__main__":
#     import sys
    
#     if len(sys.argv) > 1 and sys.argv[1] == "server":
#         start_server()
#     else:
#         main()

# For local testing only
if __name__ == "__main__":
    from http.server import HTTPServer
    
    PORT = 8000
    print(f"Local server running at http://localhost:{PORT}")
    
    try:
        httpd = HTTPServer(("localhost", PORT), handler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
