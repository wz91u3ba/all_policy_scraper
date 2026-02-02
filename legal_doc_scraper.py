"""
Legal Document Scraper for MinutePolicy Lead Qualification
Scrapes a website, identifies legal documents, returns content as rich text.

Deploy on Railway/Render, trigger via Make.com webhook from Airtable.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, request, jsonify
from anthropic import Anthropic

app = Flask(__name__)

# Document types we're looking for
DOCUMENT_TYPES = {
    "R01_terms_and_conditions": [
        "terms", "terms of service", "terms and conditions", "terms of use", 
        "tos", "user agreement", "service agreement"
    ],
    "R02_privacy_policy": [
        "privacy", "privacy policy", "privacy notice", "data policy",
        "data protection", "privacy statement"
    ],
    "R03_ada_acc_statement": [
        "accessibility", "ada", "accessibility statement", "wcag",
        "accessible", "disability", "a11y"
    ],
    "R04_cookie_usage_policy": [
        "cookie", "cookies", "cookie policy", "cookie notice",
        "cookie preferences", "tracking"
    ],
    "R05_ai_usage_policy_disclaimer": [
        "ai policy", "ai disclaimer", "artificial intelligence", "ai usage",
        "machine learning", "automated decision", "ai disclosure"
    ],
    "R06_refund_and_return_policy": [
        "refund", "return", "returns", "refund policy", "return policy",
        "money back", "cancellation", "exchange policy"
    ],
    "R07_dmca_slash_copyright_policy": [
        "dmca", "copyright", "intellectual property", "ip policy",
        "copyright notice", "takedown", "infringement"
    ]
}

# Keywords to find legal links in general
LEGAL_KEYWORDS = [
    "terms", "privacy", "legal", "policy", "cookie", "accessibility",
    "refund", "return", "dmca", "copyright", "disclaimer", "ai",
    "conditions", "notice", "compliance", "gdpr"
]


def get_page_content(url: str, timeout: int = 10) -> tuple[str, str]:
    """Fetch a page and return (html, text) tuple."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "header"]):
            element.decompose()
        
        text = soup.get_text(separator="\n", strip=True)
        return response.text, text
    except Exception as e:
        return "", ""


def find_legal_links(html: str, base_url: str) -> list[dict]:
    """Extract all potential legal document links from a page."""
    soup = BeautifulSoup(html, "html.parser")
    legal_links = []
    seen_urls = set()
    
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        
        # Build absolute URL
        full_url = urljoin(base_url, href)
        
        # Skip if already seen or external
        if full_url in seen_urls:
            continue
        
        # Check if link text or href contains legal keywords
        href_lower = href.lower()
        is_legal = any(
            kw in text or kw in href_lower 
            for kw in LEGAL_KEYWORDS
        )
        
        if is_legal:
            seen_urls.add(full_url)
            legal_links.append({
                "url": full_url,
                "text": link.get_text(strip=True),
                "href": href
            })
    
    return legal_links


def classify_document_with_ai(url: str, text: str, link_text: str) -> dict:
    """Use Claude to classify which document type this is and extract key content."""
    
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # Truncate text to avoid token limits
    text_preview = text[:8000] if len(text) > 8000 else text
    
    prompt = f"""Analyze this legal document and classify it.

URL: {url}
Link Text: {link_text}

Document Content:
{text_preview}

Classify this document into ONE of these categories (or "unknown" if it doesn't fit):
- R01_terms_and_conditions (Terms of Service, User Agreement, etc.)
- R02_privacy_policy (Privacy Policy, Data Protection, etc.)
- R03_ada_acc_statement (Accessibility Statement, ADA Compliance, WCAG)
- R04_cookie_usage_policy (Cookie Policy, Tracking Notice)
- R05_ai_usage_policy_disclaimer (AI Usage Policy, AI Disclosure)
- R06_refund_and_return_policy (Refund Policy, Return Policy, Cancellation)
- R07_dmca_slash_copyright_policy (DMCA, Copyright Policy, IP Policy)

Return JSON only:
{{
    "category": "R0X_category_name or unknown",
    "confidence": 0.0-1.0,
    "summary": "2-3 sentence summary of what this document covers"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result_text = response.content[0].text
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"AI classification error: {e}")
    
    return {"category": "unknown", "confidence": 0, "summary": ""}


def convert_to_rich_text(text: str, url: str, summary: str) -> str:
    """Convert document content to Airtable-friendly rich text (Markdown)."""
    
    # Clean and truncate
    clean_text = re.sub(r'\n{3,}', '\n\n', text)
    truncated = clean_text[:5000] if len(clean_text) > 5000 else clean_text
    
    rich_text = f"""**Source:** [{url}]({url})

**Summary:** {summary}

---

{truncated}

{"..." if len(clean_text) > 5000 else ""}
"""
    return rich_text


def scrape_legal_documents(target_url: str) -> dict:
    """Main function: scrape a URL and return all legal documents found."""
    
    # Initialize results with "None" for all document types
    results = {doc_type: "None" for doc_type in DOCUMENT_TYPES.keys()}
    results["_meta"] = {
        "url": target_url,
        "links_found": 0,
        "documents_identified": 0
    }
    
    # Fetch the main page
    html, _ = get_page_content(target_url)
    if not html:
        results["_meta"]["error"] = "Could not fetch main page"
        return results
    
    # Find all legal links
    legal_links = find_legal_links(html, target_url)
    results["_meta"]["links_found"] = len(legal_links)
    
    # Also check common legal page paths
    common_paths = [
        "/terms", "/terms-of-service", "/tos", "/terms-and-conditions",
        "/privacy", "/privacy-policy",
        "/accessibility", "/ada",
        "/cookies", "/cookie-policy",
        "/refund", "/refund-policy", "/returns",
        "/dmca", "/copyright",
        "/legal", "/policies"
    ]
    
    parsed = urlparse(target_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    for path in common_paths:
        full_url = base + path
        if full_url not in [l["url"] for l in legal_links]:
            legal_links.append({
                "url": full_url,
                "text": path.strip("/").replace("-", " ").title(),
                "href": path
            })
    
    # Process each legal link
    documents_found = 0
    
    for link in legal_links:
        _, text = get_page_content(link["url"])
        if not text or len(text) < 100:
            continue
        
        # Classify with AI
        classification = classify_document_with_ai(
            link["url"], 
            text, 
            link["text"]
        )
        
        category = classification.get("category", "unknown")
        confidence = classification.get("confidence", 0)
        summary = classification.get("summary", "")
        
        # Only accept if confidence is reasonable and category is valid
        if category in DOCUMENT_TYPES and confidence >= 0.6:
            # Don't overwrite if we already found this type (keep first/best)
            if results[category] == "None":
                results[category] = convert_to_rich_text(
                    text, 
                    link["url"],
                    summary
                )
                documents_found += 1
    
    results["_meta"]["documents_identified"] = documents_found
    
    return results


# === API Endpoint for Make.com ===

@app.route("/scrape", methods=["POST"])
def scrape_endpoint():
    """Webhook endpoint for Make.com integration."""
    
    data = request.json or {}
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    # Ensure URL has scheme
    if not url.startswith("http"):
        url = "https://" + url
    
    try:
        results = scrape_legal_documents(url)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # For local testing
    import sys
    
    if len(sys.argv) > 1:
        # CLI mode: python legal_doc_scraper.py https://example.com
        test_url = sys.argv[1]
        print(f"Scraping: {test_url}\n")
        results = scrape_legal_documents(test_url)
        print(json.dumps(results, indent=2))
    else:
        # Server mode
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
