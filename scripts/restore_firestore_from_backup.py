#!/usr/bin/env python3
"""Restore Firestore documents from a JSONL REST export into (default).

Usage:
  gcloud auth print-access-token >/dev/null
  python3 scripts/restore_firestore_from_backup.py scripts/firestore-us-backup-YYYYMMDD.jsonl
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = "swaasth-5bf90"
DATABASE = "(default)"


def access_token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True
    ).strip()


def patch_document(token: str, name: str, fields: dict) -> None:
    # Rewrite database id in resource name if needed
    if "/databases/" in name:
        prefix, rest = name.split("/databases/", 1)
        _old_db, _, doc_path = rest.partition("/")
        name = f"{prefix}/databases/{DATABASE}/{doc_path}"

    url = (
        f"https://firestore.googleapis.com/v1/{name}"
        f"?currentDocument.exists=false"
    )
    body = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        # Already exists — overwrite with merge-style patch
        if exc.code == 409:
            url = f"https://firestore.googleapis.com/v1/{name}"
            req = urllib.request.Request(
                url,
                data=body,
                method="PATCH",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req) as resp:
                resp.read()
            return
        raise


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Backup not found: {path}", file=sys.stderr)
        return 1

    token = access_token()
    docs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    # Parents before children (shorter paths first)
    docs.sort(key=lambda d: d["name"].count("/"))

    ok = 0
    for doc in docs:
        fields = doc.get("fields") or {}
        for attempt in range(5):
            try:
                patch_document(token, doc["name"], fields)
                ok += 1
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if attempt == 4:
                    print(f"FAILED {doc['name']}: {exc.code} {detail}", file=sys.stderr)
                    return 1
                time.sleep(1.5 * (attempt + 1))
                token = access_token()

    print(f"Restored {ok}/{len(docs)} documents into {PROJECT} / {DATABASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
