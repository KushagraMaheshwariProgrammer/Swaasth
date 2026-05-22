#!/usr/bin/env python3
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

API_URL = "https://nabh.co/wp-admin/admin-ajax.php"
REFERER = "https://nabh.co/find-a-healthcare-organisation/"
OUTPUT_CSV = Path("nabh_accredited_hospitals.csv")
PAGE_DELAY_SECONDS = 0.05
MAX_RETRIES = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://nabh.co",
    "Referer": REFERER,
    "X-Requested-With": "XMLHttpRequest",
}

COLUMNS = ["HCO Name", "Address", "Contact", "Accreditation Number (Acc. No.)", "Accreditations / Certifications"]

class RowParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_row = None
        self.current_col = None
        self.depth = 0
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div" and "organisation-list" in classes:
            self.current_row = {key: [] for key in ("name", "address", "contact", "acc_no", "certs")}
            self.depth = 1
            self.current_col = None
            return
        if self.current_row is None:
            return
        if tag == "div":
            self.depth += 1
        if tag in {"script", "style"}:
            self.skip_depth += 1
        for class_name, column in (("hs-col-1", "name"), ("hs-col-2", "address"), ("hs-col-3", "contact"), ("hs-col-4", "acc_no"), ("hs-col-5", "certs")):
            if class_name in classes:
                self.current_col = column
                break

    def handle_endtag(self, tag):
        if self.current_row is None:
            return
        if tag in {"script", "style"}:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag == "div":
            self.depth -= 1
            if self.depth <= 0:
                self.rows.append({key: normalize(" ".join(value)) for key, value in self.current_row.items()})
                self.current_row = None
                self.current_col = None
                self.depth = 0

    def handle_data(self, data):
        if self.current_row is None or self.current_col is None or self.skip_depth:
            return
        text = normalize(data)
        if text:
            self.current_row[self.current_col].append(text)

def normalize(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()

def post_page(page):
    payload = urllib.parse.urlencode({"q": "", "lat": "", "long": "", "action": "get_hospitals", "page": str(page), "selectedSpecText": ""}).encode("utf-8")
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = urllib.request.Request(API_URL, data=payload, headers=HEADERS, method="POST")
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            sleep_for = min(2 ** attempt, 30)
            print(f"Retrying page {page} after {type(exc).__name__}: {exc} (sleep {sleep_for}s)", file=sys.stderr)
            time.sleep(sleep_for)
    raise RuntimeError(f"Failed page {page} after {MAX_RETRIES} attempts: {last_error}")

def parse_rows(html_text):
    parser = RowParser()
    parser.feed(html_text or "")
    rows = []
    for row in parser.rows:
        rows.append({
            "HCO Name": row["name"],
            "Address": row["address"],
            "Contact": row["contact"] or "NA",
            "Accreditation Number (Acc. No.)": row["acc_no"],
            "Accreditations / Certifications": dedupe_certifications(row["certs"]),
        })
    return rows

def dedupe_certifications(value):
    known = ["Accredited", "Certified", "Empaneled", "Certification", "Entry Level", "MOU"]
    found = []
    lower = value.lower()
    for item in known:
        if item.lower() in lower and item not in found:
            found.append(item)
    return "; ".join(found) if found else normalize(value)

def main():
    first = post_page(1)
    pagination = first.get("pagination") or {}
    total_pages = int(pagination.get("total_pages") or 1)
    total_results = int(pagination.get("total_results") or 0)
    print(f"API: POST {API_URL}")
    print("Payload: action=get_hospitals, q=, lat=, long=, selectedSpecText=, page=<page>")
    print(f"Pagination: {total_pages} pages, {total_results} reported results")

    written = 0
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        for page in range(1, total_pages + 1):
            data = first if page == 1 else post_page(page)
            rows = parse_rows(data.get("html", ""))
            writer.writerows(rows)
            written += len(rows)
            if page == 1 or page % 25 == 0 or page == total_pages:
                print(f"Fetched page {page}/{total_pages}; rows written: {written}")
            if page < total_pages:
                time.sleep(PAGE_DELAY_SECONDS)

    print(f"Done: wrote {written} rows to {OUTPUT_CSV.resolve()}")
    if total_results and written != total_results:
        print(f"Warning: reported total_results={total_results}, parsed rows={written}", file=sys.stderr)

if __name__ == "__main__":
    main()
