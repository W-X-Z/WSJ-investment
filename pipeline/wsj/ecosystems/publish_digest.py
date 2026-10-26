"""Publish a daily research digest into one persistent GitHub issue per ISO week.

GH Actions artifacts retain the machine-readable checkpoint; weekly issue comments
preserve human-readable research history without pushing data commits to main
(which would otherwise rebuild Vercel every six hours).

Requires GITHUB_TOKEN/ GH_TOKEN with issues:write on default branch. Never posts
on PRs. Notifications depend on the owner's GitHub watch settings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GITHUB_API = "https://api.github.com"
KST = ZoneInfo("Asia/Seoul")


def issue_title(now: datetime) -> str:
    local = now.astimezone(KST)
    iso = local.isocalendar()
    return f"Technology Intelligence | {iso.year}-W{iso.week:02d}"


def request_api(path: str, *, token: str, method: str = "GET",
                payload: dict | None = None) -> dict | list:
    if not path.startswith("/repos/") or ".." in path:
        raise ValueError("Refuse path outside repository endpoint")
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = Request(GITHUB_API + path, data=body, method=method, headers={
        "Authorization": "Bearer " + token, "User-Agent": "WSJ-investment-research-monitor",
        "Accept": "application/vnd.github+json", "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read(200_000))


def find_issue(repo: str, title: str, token: str) -> int | None:
    # Paginate instead of assuming the latest 100 issues are enough.
    for page in range(1, 6):
        items = request_api(f"/repos/{repo}/issues?state=all&per_page=100&page={page}", token=token)
        if not items:
            break
        for issue in items:
            if issue.get("title") == title and "pull_request" not in issue:
                return int(issue["number"])
        if len(items) < 100:
            break
    return None


def publish(repo: str, token: str, report_path: Path, run_url: str,
            now: datetime | None = None) -> dict:
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError("Expected owner/repo")
    now = now or datetime.now(KST)
    title = issue_title(now)
    report = report_path.read_text(encoding="utf-8").strip()
    content = f"### Daily technology research · {now.astimezone(KST).strftime('%Y-%m-%d %H:%M KST')}\n\n"
    content += report[:44_000] + "\n\n"
    content += f"[Original workflow run and machine-readable artifacts]({run_url})\n"
    number = find_issue(repo, title, token)
    if number is None:
        result = request_api(f"/repos/{repo}/issues", token=token, method="POST",
                             payload={"title": title, "body": content})
        return {"issue": result["number"], "url": result["html_url"], "created": True}
    result = request_api(f"/repos/{repo}/issues/{number}/comments",
                         token=token, method="POST", payload={"body": content})
    return {"issue": number, "url": result["html_url"], "created": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist tech research digest in weekly GitHub issue")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_url = f"https://github.com/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    if args.dry_run:
        print(json.dumps({"title": issue_title(datetime.now(KST)), "report": str(args.report),
                          "repo": repo, "will_write": False}, ensure_ascii=False))
        return 0
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token or not repo or not os.environ.get("GITHUB_RUN_ID"):
        raise SystemExit("GH_TOKEN, GITHUB_REPOSITORY and GITHUB_RUN_ID are required.")
    result = publish(repo, token, args.report, run_url)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
