"""
Legal Document Scraper v2 - FAST VERSION
Just finds links, doesn't overthink it.
~3-5 seconds per site instead of 60+
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request, jsonify

app = Flask(__name__)

# Simple keyword matching - no AI needed for detection
DOCUMENT_PATTERNS = {
    "R01_terms_and_conditions": [
        "terms of service", "terms and conditions", "terms of use", 
        "terms & conditions", "user agreement", "tos", "terms"
    ],
    "R02_privacy_policy": [
        "privacy policy", "privacy notice", "privacy statement", "privacy"
    ],
    "R03_ada_acc_statement": [
        "accessibility", "ada compliance", "accessibility statement", "wcag"
    ],
    "R04_cookie_usage_policy": [
        "cookie policy", "cookie notice", "cookies"
    ],
    "R05_ai_usage_policy_disclaimer": [
        "ai policy", "ai disclaimer", "ai usage", "artificial intelligence policy"
    ],
    "R06_refund_and_return_policy": [
        "refund policy", "return policy", "refund & return", "returns", 
        "money back", "cancellation policy"
    ],
    "R07_dmca_slash_copyright_policy": [
        "dmca", "copyright policy", "copyright notice", "intellectual property"
    ]
}


def get_page(url: str, timeout: int = 10) -> str:
    """Fetch a page, return HTML or empty string."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return ""


def find_legal_links(html: str, base_url: str) -> dict:
    """
    Scan page for legal document links.
    Returns dict of document_type -> URL string or "None"
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Initialize results
    results = {doc_type: "None" for doc_type in DOCUMENT_PATTERNS.keys()}
    
    # Get all links
    all_links = soup.find_all("a", href=True)
    
    for link in all_links:
        href = link.get("href", "").strip()
        link_text = link.get_text(strip=True).lower()
        href_lower = href.lower()
        
        # Skip empty or javascript links
        if not href or href.startswith("javascript:") or href == "#":
            continue
        
        # Build absolute URL
        full_url = urljoin(base_url, href)
        
        # Check each document type
        for doc_type, patterns in DOCUMENT_PATTERNS.items():
            # Skip if already found
            if results[doc_type] != "None":
                continue
                
            # Check if any pattern matches link text or href
            for pattern in patterns:
                pattern_slug = pattern.replace(" ", "-")
                pattern_compact = pattern.replace(" ", "")
                
                if (pattern in link_text or 
                    pattern_slug in href_lower or 
                    pattern_compact in href_lower):
                    # Format as clickable markdown link
                    display_text = link.get_text(strip=True) or pattern.title()
                    results[doc_type] = f"[{display_text}]({full_url})"
                    break
    
    return results


def scrape_legal_documents(target_url: str) -> dict:
    """Main function: scrape a URL and return all legal documents found."""
    
    # Ensure URL has scheme
    if not target_url.startswith("http"):
        target_url = "https://" + target_url
    
    # Initialize results
    results = {doc_type: "None" for doc_type in DOCUMENT_PATTERNS.keys()}
    results["_meta"] = {
        "url": target_url,
        "status": "pending"
    }
    
    # Fetch the main page
    html = get_page(target_url)
    
    if not html:
        results["_meta"]["status"] = "failed_to_fetch"
        results["_meta"]["error"] = "Could not load the website"
        return results
    
    # Find legal links
    found = find_legal_links(html, target_url)
    results.update(found)
    
    # Count what we found
    found_count = sum(1 for k, v in results.items() if k.startswith("R0") and v != "None")
    results["_meta"]["status"] = "success"
    results["_meta"]["documents_found"] = found_count
    
    return results


# === API Endpoints ===

@app.route("/scrape", methods=["POST"])
def scrape_endpoint():
    """Webhook endpoint for Make.com integration."""
    
    data = request.json or {}
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    try:
        results = scrape_legal_documents(url)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# === CLI for testing ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        print(f"Scraping: {test_url}\n")
        results = scrape_legal_documents(test_url)
        print(json.dumps(results, indent=2))
    else:
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
