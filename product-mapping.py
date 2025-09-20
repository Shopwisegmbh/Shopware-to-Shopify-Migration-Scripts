#!/usr/bin/env python3
import sys, json, csv, re, math, argparse

HEADERS = [
  "Handle","Title","Body (HTML)","Vendor","Product Category","Type","Tags","Published",
  "Option1 Name","Option1 Value","Option2 Name","Option2 Value","Option3 Name","Option3 Value",
  "Variant SKU","Variant Grams","Variant Inventory Tracker","Variant Inventory Qty","Variant Inventory Policy","Variant Fulfillment Service",
  "Variant Price","Variant Compare At Price","Variant Requires Shipping","Variant Taxable","Variant Barcode",
  "Image Src","Image Position","Image Alt Text","Gift Card",
  "SEO Title","SEO Description","Google Shopping / Google Product Category","Google Shopping / Gender","Google Shopping / Age Group","Google Shopping / MPN","Google Shopping / Condition","Google Shopping / Custom Product",
  "Variant Image","Variant Weight Unit","Variant Tax Code","Cost per item",
  "Included / United States","Price / United States","Compare At Price / United States",
  "Included / International","Price / International","Compare At Price / International",
  "Status"
]

def slugify(s: str) -> str:
    if not s: return "produkt"
    s = s.lower().strip()
    for k,v in {"ä":"ae","ö":"oe","ü":"ue","ß":"ss"}.items(): s = s.replace(k,v)
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "produkt"

def idx_included(included):
    return {(o.get("type"), o.get("id")): o for o in (included or [])}

def attr(o): 
    return (o or {}).get("attributes", {}) if isinstance(o, dict) else {}

def rel_ids(o, key):
    r = (o or {}).get("relationships", {}).get(key, {})
    d = r.get("data")
    if d is None: return []
    if isinstance(d, list): return [(i.get("type"), i.get("id")) for i in d if i.get("id")]
    if isinstance(d, dict): return [(d.get("type"), d.get("id"))] if d.get("id") else []
    return []

def resolve(idx, start, chain):
    cur = idx.get(start)
    if not cur: return None
    for k in chain:
        lst = rel_ids(cur, k)
        if not lst: return None
        cur = idx.get(lst[0])
        if not cur: return None
    return cur

def money_first(a_list):
    arr = (a_list or [])
    if isinstance(arr, list) and arr:
        g = arr[0].get("gross")
        try: return f"{float(g):.2f}" if g is not None else ""
        except: return ""
    return ""

def compare_at_first(a_list):
    arr = (a_list or [])
    if isinstance(arr, list) and arr:
        lp = arr[0].get("listPrice")
        if isinstance(lp, dict):
            g = lp.get("gross")
            try: return f"{float(g):.2f}" if g is not None else ""
            except: pass
        rp = arr[0].get("regulationPrice")
        if isinstance(rp, dict):
            g = rp.get("gross")
            try: return f"{float(g):.2f}" if g is not None else ""
            except: pass
    return ""

def cost_first(a_list):
    arr = (a_list or [])
    if isinstance(arr, list) and arr:
        g = arr[0].get("gross")
        try: return f"{float(g):.2f}" if g is not None else ""
        except: return ""
    return ""

def grams(weight):
    try:
        w = float(weight)
        if w <= 0: return ""  # lieber leer als 0 erzwingen
        return str(int(round(w * 1000)))
    except:
        return ""

def images_for(entity, idx):
    out = []
    cov = rel_ids(entity, "cover")
    if cov:
        m = resolve(idx, cov[0], ["media"])
        u = attr(m).get("url")
        if u: out.append(u)
    for pm in rel_ids(entity, "media"):
        m = resolve(idx, pm, ["media"])
        u = attr(m).get("url")
        if u and u not in out: out.append(u)
    return out

def vendor_for(prod, idx):
    mids = rel_ids(prod, "manufacturer")
    if mids:
        man = idx.get(mids[0])
        if man: return attr(man).get("name") or ""
    return ""

def seo_for(prod):
    a = attr(prod)
    seo_title = a.get("metaTitle") or a.get("translated",{}).get("metaTitle") or ""
    seo_desc  = a.get("metaDescription") or a.get("translated",{}).get("metaDescription") or ""
    return seo_title, seo_desc

def option_pairs(prod, idx):
    out = []
    for oid in rel_ids(prod, "options"):
        opt = idx.get(oid)
        if not opt: continue
        oa = attr(opt)
        val = oa.get("translated",{}).get("name") or oa.get("name")
        grp = resolve(idx, oid, ["group"])
        gname = attr(grp).get("translated",{}).get("name") or attr(grp).get("name") if grp else None
        if gname and val:
            out.append((gname, val))
    return out

def stable_group_order(children, idx):
    groups = set()
    for ch in children:
        for g,_ in option_pairs(ch, idx):
            groups.add(g)
    rest = sorted([g for g in groups if g != "Inhalt"])
    return (["Inhalt"] if "Inhalt" in groups else []) + rest[:2]  # max 3 Gruppen

def category_ids_tags(prod):
    return ",".join([cid for (_t,cid) in rel_ids(prod, "categories")])

def build_rows_for_family(parent, idx, images_mode="rows", img_sep=","):
    rows = []
    a = attr(parent)
    handle = slugify(a.get("name") or a.get("translated",{}).get("name"))
    vendor = vendor_for(parent, idx)
    seo_title, seo_desc = seo_for(parent)
    parent_images = images_for(parent, idx)
    tags = category_ids_tags(parent)
    parent_active = bool(a.get("active", True))
    published_val = "TRUE" if parent_active else "FALSE"

    child_ids = rel_ids(parent, "children")
    children = [idx.get(c) for c in child_ids if idx.get(c)]

    def blank_row():
        return {h:"" for h in HEADERS}

    # -------- Einfaches Produkt --------
    if not children:
        r = blank_row()
        r.update({
            "Handle": handle,
            "Title": a.get("name") or a.get("translated",{}).get("name") or "",
            "Body (HTML)": a.get("description") or a.get("translated",{}).get("description") or "",
            "Vendor": vendor,
            "Tags": tags,
            "Published": published_val,
            "Option1 Name": "Title",
            "Option1 Value": "Default Title",
            "Variant SKU": a.get("productNumber") or "",
            "Variant Grams": grams(a.get("weight")),
            "Variant Inventory Tracker": "shopify",
            "Variant Inventory Qty": a.get("stock") or 0,
            "Variant Inventory Policy": "deny",
            "Variant Fulfillment Service": "manual",
            "Variant Price": money_first(a.get("price")),
            "Variant Compare At Price": compare_at_first(a.get("price")),
            "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE",
            "Variant Barcode": a.get("ean") or "",
            "Gift Card": "FALSE",
            "SEO Title": seo_title,
            "SEO Description": seo_desc,
            "Google Shopping / Condition": "new",
            "Variant Weight Unit": "g",
            "Cost per item": cost_first(a.get("purchasePrices")),
            "Status": "active"
        })
        if images_mode == "cell":
            r["Image Src"] = img_sep.join(parent_images) if parent_images else ""
            r["Image Position"] = "1" if parent_images else ""
            rows.append(r)
        else:
            if parent_images:
                r["Image Src"] = parent_images[0]
                r["Image Position"] = "1"
            rows.append(r)
            pos = 2
            for img in parent_images[1:]:
                rimg = blank_row()
                rimg["Handle"] = handle
                rimg["Image Src"] = img
                rimg["Image Position"] = str(pos)
                rows.append(rimg)
                pos += 1
        return rows

    # -------- Variantenprodukt --------
    group_order = stable_group_order(children, idx)    # z. B. ["Farbe","Grösse"]
    gallery = list(parent_images)
    first = True

    def values_for(child):
        pairs = dict(option_pairs(child, idx))
        return [pairs.get(g, "") for g in group_order]

    for ch in children:
        ca = attr(ch)
        r = blank_row()
        r["Handle"] = handle

        if first:
            r.update({
                "Title": a.get("name") or a.get("translated",{}).get("name") or "",
                "Body (HTML)": a.get("description") or a.get("translated",{}).get("description") or "",
                "Vendor": vendor,
                "Tags": tags,
                "Published": "TRUE",
                "Gift Card": "FALSE",
                "SEO Title": seo_title,
                "SEO Description": seo_desc,
                "Google Shopping / Condition": "new",
                "Status": "active",
            })
            for i,g in enumerate(group_order[:3], start=1):
                r[f"Option{i} Name"] = g

        vals = values_for(ch)
        if len(vals) > 0 and vals[0]: r["Option1 Value"] = vals[0]
        if len(vals) > 1 and vals[1]: r["Option2 Value"] = vals[1]
        if len(vals) > 2 and vals[2]: r["Option3 Value"] = vals[2]

        r["Variant SKU"] = ca.get("productNumber") or ""

        # Gewicht: zuerst Child → Fallback Parent
        g = grams(ca.get("weight"))
        if not g: g = grams(a.get("weight"))
        r["Variant Grams"] = g

        r["Variant Inventory Tracker"] = "shopify"
        r["Variant Inventory Qty"] = ca.get("stock") or 0
        r["Variant Inventory Policy"] = "deny"
        r["Variant Fulfillment Service"] = "manual"

        # Preis + Compare At Price: Child → Fallback Parent
        price = money_first(ca.get("price")) or money_first(a.get("price"))
        r["Variant Price"] = price
        cmp = compare_at_first(ca.get("price")) or compare_at_first(a.get("price"))
        r["Variant Compare At Price"] = cmp

        r["Variant Requires Shipping"] = "TRUE"
        r["Variant Taxable"] = "TRUE"
        r["Variant Barcode"] = ca.get("ean") or ""
        r["Variant Weight Unit"] = "g"

        cost = cost_first(ca.get("purchasePrices")) or cost_first(a.get("purchasePrices"))
        r["Cost per item"] = cost

        v_imgs = images_for(ch, idx)
        if first and images_mode == "rows" and parent_images:
            r["Image Src"] = parent_images[0]
            r["Image Position"] = "1"
        if v_imgs:
            r["Variant Image"] = v_imgs[0]
            if v_imgs[0] not in gallery:
                gallery.append(v_imgs[0])

        rows.append(r)
        first = False

    if images_mode == "rows":
        pos = 2 if parent_images else 1
        start = 1 if parent_images else 0
        for img in gallery[start:]:
            rimg = {h:"" for h in HEADERS}
            rimg["Handle"] = handle
            rimg["Image Src"] = img
            rimg["Image Position"] = str(pos)
            rows.append(rimg)
            pos += 1
    else:
        if rows:
            rows[0]["Image Src"] = img_sep.join(gallery) if gallery else ""
            rows[0]["Image Position"] = "1" if gallery else ""

    return rows

def main():
    ap = argparse.ArgumentParser(description="SW6 → Shopify CSV mapper (v02, stabil & mit Fallbacks)")
    ap.add_argument("input_json")
    ap.add_argument("output_csv")
    ap.add_argument("--images", choices=["rows","cell"], default="rows",
                    help="rows: Shopify-konform (zusätzliche Bildzeilen); cell: alle Bild-URLs in einer Zelle")
    ap.add_argument("--img-sep", default=",", help="Separator für --images cell (Standard ,)")
    args = ap.parse_args()

    data = json.load(open(args.input_json, encoding="utf-8"))
    idx = idx_included(data.get("included", []))

    outrows = []
    for prod in data.get("data", []):
        if attr(prod).get("parentId") is None:
            outrows.extend(build_rows_for_family(prod, idx, images_mode=args.images, img_sep=args.img_sep))

    with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(outrows)

    print(f"Wrote {len(outrows)} rows to {args.output_csv} (images mode: {args.images})")

if __name__ == "__main__":
    main()
