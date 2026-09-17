"""Read-only internship discovery and fail-closed official ATS verification.

The community index supplies leads. Only a current official Greenhouse record
with an explicit Summer 2027 term can establish activity. No application is sent.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

INDEX_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md"
DEFAULT_BOARDS = ("scaleai", "verkada", "schonfeld", "sage49", "waymo", "andurilindustries", "databricks", "figma")
COMPANIES = {"scaleai": "Scale AI", "verkada": "Verkada", "schonfeld": "Schonfeld", "sage49": "Sage", "waymo": "Waymo", "andurilindustries": "Anduril", "databricks": "Databricks", "figma": "Figma"}
TIMEOUT = 15
MAX_BYTES = 12_000_000
ROLE_PATTERN = re.compile(r"software|\bSWE\b|backend|back.end|full.stack|machine learning|data scien|data analy|data engineer|computer vision|artificial intelligence|\bAI\b|\bML\b|platform engineer|infrastructure engineer|site reliability|FPGA|quantitative|\bquant\b", re.I)
_CLOSED = re.compile(r"\b(?:this (?:job|position|role|opening) (?:is |has been )?(?:closed|filled|no longer available)|(?:we are |is )?no longer accepting applications|job (?:not found|no longer available)|position has been filled)\b", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def validate_public_url(url, *, resolve=True):
    """Reject credentials, non-HTTPS URLs, nonstandard ports and private hosts."""
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs without embedded credentials are allowed")
    if parsed.port not in (None, 443):
        raise ValueError("Only the HTTPS port is allowed")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private network addresses are not allowed")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve:
            return url
        addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private or special-use network addresses are not allowed")
    return url


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url, *, max_bytes=MAX_BYTES):
    validate_public_url(url)
    request = Request(url, headers={"User-Agent": "InternshipPreparation/1.0 (read-only job verification)", "Accept": "application/json,text/html,text/plain"})
    with build_opener(_SafeRedirect()).open(request, timeout=TIMEOUT) as response:
        validate_public_url(response.url)
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Response exceeds the bounded download limit")
        return data.decode("utf-8", errors="replace")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "form"):
            self.ignored += 1
        if tag in ("p", "li", "br", "h1", "h2", "h3", "h4", "div") and not self.ignored:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "form"):
            self.ignored = max(0, self.ignored - 1)
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "div") and not self.ignored:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def html_text(value):
    parser = _Text()
    parser.feed(unescape(value or ""))
    return "\n".join(re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines() if line.strip())


def is_summer_2027(title, description):
    """Do not promote 2026, unspecified-year or winter-only index leads."""
    text = f"{title}\n{description}"
    if re.search(r"\b(?:winter|spring|fall|autumn)\b", title, re.I) and not re.search(r"\bsummer\b", title, re.I):
        return False
    if re.search(r"(?:summer\s*[,/-]?\s*2027|2027\s*[,/-]?\s*summer)", text, re.I):
        return True
    return bool(re.search(r"\b2027\b", title) and re.search(r"\bsummer\b", description, re.I) and not re.search(r"\bsummer\s+202[0-689]\b", description, re.I))


def is_internship(title):
    """Require an internship title, excluding co-mingled permanent/new-grad roles.

    Full-time hours, graduate-student internships and a later return offer do
    not make an internship a full-time graduate vacancy.
    """
    title = str(title or '')
    if not re.search(r"\bintern(?:ship)?s?\b", title, re.I):
        return False
    excluded = r"\b(?:new[ -]?grads?|new[ -]?graduates?|recent graduates?|entry[ -]level|permanent)\b|\binterns?\s*[/&]\s*graduates?\b|(?:/|\bor\b|\band\b|&)\s*full[ -]?time\b|\bfull[ -]?time\s*(?:/|\bor\b|\band\b|&)"
    return not re.search(excluded, title, re.I)


def is_relevant(title):
    return bool(is_internship(title) and (ROLE_PATTERN.search(title) or re.search(r'\btrad(?:er|ing)\b', title, re.I))
                and not re.search(r"software support|customer care|people & culture|sales|marketing|recruit",title,re.I))


def canonical_url(url):
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if not key.startswith("utm_") and key not in ("ref", "source", "gh_src")]
    return urlunparse(parsed._replace(query=urlencode(query), fragment=""))


def stable_id(company, url):
    return hashlib.sha256((company.lower() + "|" + canonical_url(url)).encode()).hexdigest()[:20]


def greenhouse_identity(url):
    parsed = urlparse(url)
    if parsed.hostname not in ("boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"):
        return None
    match = re.fullmatch(r"/([\w-]+)/jobs/(\d+)/?", parsed.path)
    return match.groups() if match else None


def _board_job(board, raw, index_source=INDEX_URL):
    title = str(raw.get("title", ""))
    description = html_text(raw.get("content", ""))
    url = canonical_url(raw.get("absolute_url", ""))
    if not is_relevant(title) or not is_summer_2027(title, description):
        return None
    identity = greenhouse_identity(url)
    valid = identity == (board, str(raw.get("id"))) and bool(description) and not _CLOSED.search(description)
    company = COMPANIES.get(board, {"rfsmart":"RF-SMART","veeamsoftware":"Veeam","klaviyocampus":"Klaviyo","dvtrading":"DV Trading"}.get(board,board.replace("-", " ").title()))
    evidence = f"Official Greenhouse board {board} currently contains job {raw.get('id')}; title/description explicitly identify Summer 2027."
    return {
        "id": stable_id(company, url), "company": company, "title": title.strip(),
        "location": raw.get("location", {}).get("name", "Not stated"), "url": url,
        "description": description, "active": valid, "activity_evidence": evidence if valid else "Official record failed job identity, content, or closure checks",
        "verified_at": now_iso(), "term": "Summer 2027", "source_url": f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{raw.get('id')}?content=true",
        "discovery_source": index_source, "ats": "greenhouse", "board": board, "ats_id": str(raw.get("id")),
        "posted_at": raw.get("first_published", ""), "updated_at": raw.get("updated_at", ""),
        "link_working": False, "link_evidence": "Application URL has not yet been checked separately; preparation revalidates it.",
        "work_mode": "hybrid" if re.search(r"\bhybrid\b|remote days per week",raw.get("location",{}).get("name","")+" "+description,re.I) else "onsite" if re.search(r"on.site|on site|in.office|in office",description,re.I) else "remote" if re.search(r"remote",raw.get("location",{}).get("name",""),re.I) else "unknown",
    }


def refresh_jobs(*, boards=None, max_jobs=80, max_boards=14, diagnostics=None):
    """Return verified current official listings; failures produce no fake jobs.

    diagnostics is an optional caller-owned list receiving fetch errors. Discovery
    is deliberately bounded and currently supports Greenhouse only.
    """
    diagnostics = diagnostics if diagnostics is not None else []
    board_names = list(boards or DEFAULT_BOARDS)
    if boards is None:
        try:
            index = fetch_url(INDEX_URL)
            for row in re.findall(r"<tr>(.*?)</tr>", index, flags=re.S):
                cells = re.findall(r"<td>(.*?)</td>", row, flags=re.S)
                if len(cells) < 4 or not is_relevant(html_text(cells[1])) or "🔒" in row:
                    continue
                for url in re.findall(r'href="([^"]+)"', cells[3]):
                    identity = greenhouse_identity(unescape(url))
                    if identity and identity[0] not in board_names:
                        board_names.append(identity[0])
        except Exception as exc:
            diagnostics.append({"source": INDEX_URL, "error": str(exc)})
    board_names = board_names[:max_boards]

    def get_board(board):
        if not re.fullmatch(r"[\w-]+", board):
            return [], {"source": str(board), "error": "Invalid board identifier"}
        source = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        try:
            payload = json.loads(fetch_url(source))
            if not isinstance(payload.get("jobs"), list):
                raise ValueError("Missing official jobs array")
            return [job for raw in payload["jobs"] if (job := _board_job(board, raw))], None
        except Exception as exc:
            return [], {"source": source, "error": str(exc)}

    found = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        for rows, error in executor.map(get_board, board_names):
            if error:
                diagnostics.append(error)
            for job in rows:
                found[job["id"]] = job
    return list(found.values())[:max_jobs]


def verify_job(job):
    """Recheck official listing and application URL; return an updated job copy."""
    result = dict(job, active=False, link_working=False, verified_at=now_iso())
    identity = greenhouse_identity(job.get("url", ""))
    if not identity:
        from .sources.verify import verify
        return verify(job)
    board, job_id = identity
    source = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?content=true"
    try:
        raw = json.loads(fetch_url(source))
        fresh = _board_job(board, raw, job.get("discovery_source", INDEX_URL))
        if not fresh or not fresh["active"] or str(raw.get("id")) != job_id:
            raise ValueError("Official record is missing, closed, inconsistent, or not Summer 2027")
        page = fetch_url(job["url"])
        # Application forms contain a standard "no longer" option in questions;
        # exclude forms before checking closure language.
        page_text = html_text(page)
        if _CLOSED.search(page_text):
            raise ValueError("Application page says this opening is closed")
        if not page.strip() or (job_id not in page and fresh["title"].lower() not in page_text.lower()):
            raise ValueError("Application page does not identify the expected opening")
        result.update(fresh,open_status="open")
        if job.get("company"):result["company"]=job["company"]
        if job.get("id"):
            result["id"]=job["id"]
        result.update(link_working=True, link_evidence="Public application page retrieved and identifies the same official job; no closure notice outside the form.")
    except Exception as exc:
        result.update(active=False, link_working=False, activity_evidence=f"Verification failed closed: {exc}", link_evidence=str(exc))
    return result
