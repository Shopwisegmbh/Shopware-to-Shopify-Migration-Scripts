Shopware-to-Shopify Migration Scripts

Utilities to export products (including variants/options) from Shopware 6 and transform them into a Shopify CSV you can import.

Heads-up: The CSV headers and field mapping in product-mapping.py are demo defaults based on Shopify’s standard import format. Real stores often need tweaks (custom metafields, tag conventions, option naming, etc.). Adjust the mapping to your needs.

Ⅰ️⃣ Prerequisites

Python 3.9+

curl for API requests

(Optional) jq for inspecting JSON

A Shopware 6 Integration (Access Key ID + Secret Access Key) with Admin API permissions

Ⅱ️⃣ Create an Admin API token (Shopware 6)

Create an Integration in the Shopware admin:
Settings → System → Integrations → create → copy Access key ID and Secret access key.

# Your Shopware base URL (no trailing slash)
export SHOP_URL="https://your-shop-domain.tld"

# Get OAuth token
curl -s -X POST "$SHOP_URL/api/oauth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id":   "YOUR_ACCESS_KEY_ID",
    "client_secret":"YOUR_SECRET_ACCESS_KEY"
  }'


Copy the access_token from the response and export it:

export TOKEN="PASTE_ACCESS_TOKEN_HERE"

Ⅲ️⃣ Fetch products as JSON (parents + variants + associations)

Use /api/search/product and include the associations so one file has everything (children/variants, options with groups, media, tax, manufacturer, categories).

Option A — all products (mixed parents/children):

curl -s -X POST "$SHOP_URL/api/search/product" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 500,
    "page": 1,
    "associations": {
      "children": {
        "associations": {
          "options": { "associations": { "group": {} } },
          "media":   {},
          "cover":   {}
        }
      },
      "options": { "associations": { "group": {} } },
      "media": {},
      "cover": {},
      "tax": {},
      "manufacturer": {},
      "categories": {}
    }
  }' > products_page1.json


Option B — only parents (recommended): limit applies to parents, each parent carries its children.

curl -s -X POST "$SHOP_URL/api/search/product" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 500,
    "page": 1,
    "filter": [
      { "type": "equals", "field": "parentId", "value": null }
    ],
    "associations": {
      "children": {
        "associations": {
          "options": { "associations": { "group": {} } },
          "media":   {},
          "cover":   {}
        }
      },
      "options": { "associations": { "group": {} } },
      "media": {},
      "cover": {},
      "tax": {},
      "manufacturer": {},
      "categories": {}
    }
  }' > products_parents_p1.json


Repeat with "page": 2, "page": 3, … until all products are fetched.

Quick checks:

jq '.data | length' products_parents_p1.json
jq -r '.data[0].attributes.name' products_parents_p1.json

Ⅳ️⃣ Convert JSON → Shopify CSV

Run the mapper:

python3 product-mapping.py products_parents_p1.json shopify_import_p1.csv


Input: Shopware JSON export (parents with children and included)

Output: Shopify-compatible CSV ready for import

Images mode (if supported by your script):

Default (Shopify-conform): additional rows for gallery images (--images rows)

Single-cell gallery: join URLs in Image Src (--images cell --img-sep ";")

Example:

python3 product-mapping.py products_parents_p1.json shopify_import_p1.csv --images rows
python3 product-mapping.py products_parents_p2.json shopify_import_p2.csv --images cell --img-sep ";"

Ⅴ️⃣ Behavior & mapping notes (what the script does)

Headers are demo defaults: adjust columns to your store’s needs.

Published: respects Shopware’s parent active flag (TRUE if active, else FALSE).

Variants & options:

Stable option order per product family (prefers Inhalt first, then alphabetical; up to 3 groups).

OptionN Name is set in the first variant row; subsequent rows keep names empty and only fill values.

Prices:

Variant Price: variant price if present, otherwise falls back to the parent price.

Variant Compare At Price: from price[0].listPrice.gross (fallback regulationPrice.gross) with the same parent-fallback logic.

Cost per item: from purchasePrices[0].gross (variant → parent fallback).

Weight: Variant Grams uses variant weight; if missing, falls back to the parent weight.

Tags: category IDs are exported as tags (customize if you prefer names).

Images:

By default, the first image is on the first row; additional gallery images are extra rows with the same handle.

Variant images (if present) are set in Variant Image. If not in the gallery yet, they’re added.

Ⅵ️⃣ Known limitations

Multi-currency, price rules, and channel-specific visibility are not auto-handled.

HTML sanitization of descriptions is not part of the mapper; do it before import if needed.

Very large catalogs may require splitting files/pages to keep memory usage reasonable.

Metafields and custom attributes are out of scope (can be added if needed).

Ⅶ️⃣ Troubleshooting

401/403: token invalid or integration lacks permissions.

Huge JSON/CSV: lower limit, paginate more pages, or process one file at a time.

Missing option names: ensure associations.options includes { "associations": { "group": {} } }.

Variants mixing option order: ensure the script enforces a stable group order per family.

Empty prices or weights: verify parent-fallback logic is active in the script.
