# Shopware-to-Shopify Migration Scripts

Utilities to export products (including variants/options) from **Shopware 6** and transform them into a **Shopify CSV** you can import.

> **Heads-up:** The CSV headers and the field mapping in `product-mapping.py` are **demo defaults** based on Shopify’s standard import format. Real stores often need tweaks (custom metafields, tag conventions, option naming, channel visibility, etc.). **Adjust the mapping to your needs.**

## Ⅰ️⃣ Prerequisites

- Python 3.9+
- `curl` for API requests
- (Optional) `jq` for inspecting/merging JSON
- A Shopware 6 **Integration** (Access Key ID + Secret Access Key) with Admin API permissions

## Ⅱ️⃣ Create an Admin API token (Shopware 6)

Create an **Integration** in the Shopware admin:  
`Settings → System → Integrations` → create → copy **Access key ID** and **Secret access key**.

```bash
# Your Shopware base URL (no trailing slash)
export SHOP_URL="https://your-shop-domain.tld"

# Get OAuth token
curl -s -X POST "$SHOP_URL/api/oauth/token"   -H "Content-Type: application/json"   -d '{
    "grant_type": "client_credentials",
    "client_id":   "YOUR_ACCESS_KEY_ID",
    "client_secret":"YOUR_SECRET_ACCESS_KEY"
  }'
```

Copy the `access_token` from the response and export it:

```bash
export TOKEN="PASTE_ACCESS_TOKEN_HERE"
```

## Ⅲ️⃣ Fetch products as JSON (parents + variants + associations)

**Recommended:** fetch **only parent products** and include all associations so every parent carries its variants (`children`) and related entities.

```bash
# Page 1 (limit applies to PARENTS only)
curl -s -X POST "$SHOP_URL/api/search/product"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "limit": 500,
    "page": 1,
    "filter": [{ "type":"equals", "field":"parentId", "value": null }],
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
```

Repeat for additional pages:

```bash
# Page 3 (example; keep increasing page until empty)
curl -s -X POST "$SHOP_URL/api/search/product"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "limit": 500,
    "page": 2,
    "filter": [{ "type":"equals", "field":"parentId", "value": null }],
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
  }' > products_parents_p2.json
```

Quick checks:

```bash
# Count parents in a page
jq '.data | length' products_parents_p1.json

# Peek first product name
jq -r '.data[0].attributes.name' products_parents_p1.json
```

(Optional) merge multiple pages into one file:

```bash
jq -s '
  {
    data:      (map(.data)      | add),
    included:  (map(.included)  | add)
  }
' products_parents_p1.json products_parents_p3.json > products_all.json
```

## Ⅳ️⃣ Convert JSON → Shopify CSV

Run the mapper:

```bash
python3 product-mapping.py products_parents_p1.json shopify_import_p1.csv
```

- **Input:** Shopware JSON export (parents with `children` and `included`)
- **Output:** Shopify-compatible CSV ready for import

If your script supports image modes:

```bash
# Shopify-conform gallery (extra rows)
python3 product-mapping.py products_parents_p1.json shopify_import_p1.csv --images rows

# Single-cell gallery (URLs joined; choose your separator)
python3 product-mapping.py products_parents_p1.json shopify_import_p1_cell.csv --images cell --img-sep ";"
```

## Ⅴ️⃣ What the mapping does (default behavior)

- **Headers are demo defaults:** adjust columns to your store’s needs.
- **Published:** set from Shopware parent `active` (TRUE if active, else FALSE).
- **Variants & options:**
  - Stable option group order per product family (prefers `Inhalt` first, then alphabetical; up to 3 groups).
  - `OptionN Name` appears in the first variant row; subsequent rows keep names empty and only fill values.
- **Prices:**
  - `Variant Price`: variant price if present, otherwise parent price.
  - `Variant Compare At Price`: from `price[0].listPrice.gross` (fallback `regulationPrice.gross`), variant → parent fallback.
  - `Cost per item`: from `purchasePrices[0].gross`, variant → parent fallback.
- **Weight:** `Variant Grams` uses variant weight; if missing, falls back to parent weight.
- **Tags:** category IDs are exported as tags (customize if you prefer category names).
- **Images:**
  - Default: first image on the first row; additional gallery images as extra rows with the same handle.
  - Variant images (if present) are set in `Variant Image`. If not in the gallery yet, they’re added.

## Ⅵ️⃣ Known limitations

- Multi-currency, price rules, and channel-specific visibilities are not auto-handled.
- HTML sanitization of descriptions is not part of the mapper; clean up before import if needed.
- Very large catalogs may require splitting pages/files to keep memory usage reasonable.
- Metafields and custom attributes are out of scope by default (add as needed).

## Ⅶ️⃣ Troubleshooting

- **401/403**: token invalid or integration lacks permissions.
- **Large JSON/CSV**: reduce `limit`, paginate more, or process one page at a time.
- **Missing option names**: ensure `associations.options` includes `{ "associations": { "group": {} } }`.
- **Variant option order mixed**: ensure the script enforces a stable group order per family.
- **Empty prices/weights**: verify parent-fallback logic is enabled in the script.

## Ⅷ️⃣ License

MIT (or your preferred license).
