# Legal Document Scraper - Deployment Guide

## BLUF
Deploy to Railway in 5 minutes, wire to Make.com, trigger from Airtable.

---

## 1. Deploy to Railway (Free Tier Works)

### Option A: GitHub Deploy
1. Push these files to a GitHub repo
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Select your repo
5. Add environment variable: `ANTHROPIC_API_KEY` = your key
6. Railway auto-detects Python and deploys

### Option B: Railway CLI
```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set ANTHROPIC_API_KEY=sk-ant-xxxxx
```

Your endpoint will be: `https://your-app.railway.app/scrape`

---

## 2. Airtable Setup

Create these columns in your table:

| Column Name | Type |
|------------|------|
| URL | URL |
| Fetch | Checkbox |
| A01_terms_and_conditions | Long Text |
| A02_privacy_policy | Long Text |
| A03_ada_acc_statement | Long Text |
| A04_cookie_usage_policy | Long Text |
| A05_ai_usage_policy_disclaimer | Long Text |
| A06_refund_and_return_policy | Long Text |
| A07_dmca_slash_copyright_policy | Long Text |

---

## 3. Make.com Scenario

### Trigger: Airtable - Watch Records
- Table: Your table
- Trigger field: Fetch
- Filter: Fetch = true

### Action 1: HTTP - Make a Request
- URL: `https://your-app.railway.app/scrape`
- Method: POST
- Body type: JSON
- Body:
```json
{
  "url": "{{1.URL}}"
}
```

### Action 2: Airtable - Update Record
Map each field from the HTTP response:
- A01_terms_and_conditions: `{{2.body.A01_terms_and_conditions}}`
- A02_privacy_policy: `{{2.body.A02_privacy_policy}}`
- A03_ada_acc_statement: `{{2.body.A03_ada_acc_statement}}`
- A04_cookie_usage_policy: `{{2.body.A04_cookie_usage_policy}}`
- A05_ai_usage_policy_disclaimer: `{{2.body.A05_ai_usage_policy_disclaimer}}`
- A06_refund_and_return_policy: `{{2.body.A06_refund_and_return_policy}}`
- A07_dmca_slash_copyright_policy: `{{2.body.A07_dmca_slash_copyright_policy}}`
- Fetch: false (reset the trigger)

---

## 4. Test Locally First

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# Test with a URL
python legal_doc_scraper.py https://stripe.com

# Or run as server
python legal_doc_scraper.py
# Then POST to http://localhost:5000/scrape
```

---

## API Response Format

```json
{
  "A01_terms_and_conditions": "**Source:** [https://...](https://...)\n\n**Summary:** ...\n\n---\n\nFull text...",
  "A02_privacy_policy": "**Source:** ...",
  "A03_ada_acc_statement": "None",
  "A04_cookie_usage_policy": "None",
  "A05_ai_usage_policy_disclaimer": "None",
  "A06_refund_and_return_policy": "**Source:** ...",
  "A07_dmca_slash_copyright_policy": "None",
  "_meta": {
    "url": "https://example.com",
    "links_found": 12,
    "documents_identified": 3
  }
}
```

---

## Cost Estimate

- **Railway**: Free tier handles ~500 requests/month
- **Claude API**: ~$0.003-0.01 per website (depends on # of legal pages)
- **Make.com**: Free tier = 1000 ops/month

At scale: ~$0.01/site = $10 per 1000 sites scraped

---

## Pro Tips

1. **Rate limit yourself**: Add a 2-second delay in Make.com between records
2. **Cache results**: Don't re-scrape URLs you've already processed
3. **Lead scoring**: Sites with fewer policies = hotter MinutePolicy leads
4. **Batch processing**: Run overnight for large lists
