"""Agent-readiness eval: how well a Claude agent answers questions about the platform, with each feature for agents
taken away in turn (an ablation), and with a fetcher like that of Claude Code.

The agent gets a question (questions.yaml) and tools that reach only the platform. The answer is the set of records
the agent lists at the end; it is scored with precision, recall and F1 against the set that the SPARQL query of the
question finds in the dump of the platform. Each condition removes features from what the fetch tool returns, so the
platform itself is not changed. Run it against a copy of the platform that nothing writes to during the run.

    python evals/agent_ready/run.py --site http://localhost:5070 --key-file ~/ant_key.txt --reps 3
    python evals/agent_ready/run.py --site http://localhost:5070 --summary   # only the summary of the stored results

Results are written to .claude/hillclimb/agent-ready/<variant>/ (results.jsonl, traces/, errors.jsonl), one variant
per condition: baseline is the full platform, v1, v2, ... the conditions in the order of CONDITIONS.
"""

import argparse
import asyncio
import hashlib
import json
import random
import re
import statistics
import sys
import time
import zlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import anthropic
import httpx2 as httpx
import yaml
from markdownify import markdownify
from rdflib import Graph, URIRef
from rdflib.namespace import SDO

HERE = Path(__file__).resolve().parent
PREFIXES = ("PREFIX schema: <https://schema.org/>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
            "PREFIX bs: <https://bioschemas.org/draft_terms/>\n")
DISCOVERY = {"llms", "robots", "sitemap", "well_known", "link_header", "agent_line"}
# Each condition: the features removed from the platform, and the tools of the agent. The first is the baseline.
CONDITIONS = {
    "full": ({"removed": set(), "tools": {"fetch"}}, "The platform as it is, read with a plain HTTP tool (like curl)."),
    "html_only": ({"removed": DISCOVERY | {"jsonld_embed", "alternates", "markdown", "api"}, "tools": {"fetch"}},
                  "Only the HTML pages: no llms.txt, robots.txt, sitemap, .well-known, Link headers or agent line, no embedded JSON-LD, no other formats, no API."),
    "no_discovery": ({"removed": DISCOVERY, "tools": {"fetch"}},
                     "Without the discovery aids: llms.txt, robots.txt, the sitemap, .well-known, the Link headers and the line for agents at the end of each page."),
    "no_llms": ({"removed": {"llms"}, "tools": {"fetch"}}, "Without llms.txt."),
    "no_jsonld_embed": ({"removed": {"jsonld_embed"}, "tools": {"fetch"}}, "Without the JSON-LD embedded in the pages (<script type=application/ld+json>)."),
    "no_alternates": ({"removed": {"alternates", "markdown"}, "tools": {"fetch"}},
                      "Pages only in HTML: no content negotiation and no .jsonld, .ttl, .nt or .md addresses of pages."),
    "no_markdown": ({"removed": {"markdown"}, "tools": {"fetch"}}, "Without Markdown: no .md addresses and no text/markdown, on pages and in the API."),
    "no_openapi": ({"removed": {"openapi"}, "tools": {"fetch"}}, "Without the OpenAPI description and its documentation page (/api/docs/)."),
    "no_api": ({"removed": {"api"}, "tools": {"fetch"}}, "Without the API (/api/...); the pages and their formats stay."),
    "webfetch": ({"removed": set(), "tools": {"webfetch"}},
                 "The full platform, read only with a fetcher like that of Claude Code: the page as Markdown, summarised by a small model for the prompt."),
}
SYSTEM = """You are a research assistant of a toxicologist. Answer the question with the VHP4Safety platform at
{base}: look the answer up on the platform with your tools, and do not answer from memory.

When you are done, give a short answer, and end it with a JSON block that lists the address on the platform of each
record that answers the question:

```json
{{"answer": ["<address of a record>", "..."]}}
```"""
CHUNK = 30000
# Dollars per million input and output tokens; Haiku 5.5 costs more for a prompt over 100,000 tokens.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
LONG_PRICES = {"claude-haiku-5-5": (0.50, 2.50)}
SUFFIXES = (".jsonld", ".ttl", ".nt", ".md")


def variants() -> dict[str, str]:
    """Return the variant directory of each condition: baseline, v1, v2, ..."""
    return {name: "baseline" if index == 0 else f"v{index}" for index, name in enumerate(CONDITIONS)}


# The answers -------------------------------------------------------------------------------------------------


def golds(spec: dict, dump: Graph) -> dict[str, set[str]]:
    """Return the set of records that answers each question, from its query over the dump."""
    found = {}
    for question in spec["questions"]:
        query = re.sub(r"\bp:([A-Za-z0-9_./#-]*)", lambda match: f"<{spec['base']}{match.group(1)}>", question["gold"])
        found[question["id"]] = {str(row[0]) for row in dump.query(PREFIXES + query)}
        if not found[question["id"]]:
            raise SystemExit(f"{question['id']}: its query finds nothing in the dump")
    return found


def names(dump: Graph, base: str) -> dict[str, str]:
    """Return the record of each name that only one record has, for answers given by name."""
    seen: dict[str, set[str]] = {}
    for record, name in dump.subject_objects(SDO.name):
        if isinstance(record, URIRef) and str(record).startswith(base) and "#" not in str(record):
            seen.setdefault(str(name).casefold().strip(), set()).add(str(record))
    return {name: next(iter(found)) for name, found in seen.items() if len(found) == 1}


def answered(text: str) -> list | None:
    """Return the list in the last {"answer": [...]} of the final text, or None."""
    for block in reversed(re.findall(r"\{[^{}]*\"answer\"\s*:\s*\[.*?\]\s*\}", text, flags=re.S)):
        try:
            listed = json.loads(block)["answer"]
        except (json.JSONDecodeError, KeyError):
            continue
        if isinstance(listed, list):
            return listed
    return None


def normalized(item, base: str, site: str, named: dict[str, str]) -> str:
    """Return an answer item as the address of a record: the page address, without /api/, a format or a query."""
    text = str(item).strip()
    if not text.startswith(("http://", "https://", "/")):
        return named.get(text.casefold(), text)
    text = urljoin(base, text.replace(site.rstrip("/") + "/", base)).split("?")[0].rstrip("/")
    text = re.sub(r"^http://", "https://", text)
    if text.startswith(base + "api/"):
        text = text.replace(base + "api/", base, 1)
    for ending in SUFFIXES:
        text = text.removesuffix(ending)
    return text


def graded(listed: list | None, gold: set[str], base: str, site: str, named: dict[str, str]) -> dict:
    given = {normalized(item, base, site, named) for item in listed or []}
    hits = len(given & gold)
    precision = hits / len(given) if given else 0.0
    recall = hits / len(gold)
    return {"f1": 2 * precision * recall / (precision + recall) if hits else 0.0, "precision": precision, "recall": recall,
            "exact": float(given == gold), "answered": float(listed is not None), "_given": sorted(given)}


# The platform as the agent sees it under a condition --------------------------------------------------------------


def blocked(path: str, removed: set[str]) -> bool:
    if "llms" in removed and path in ("/llms.txt", "/llms-full.txt"):
        return True
    if ("robots" in removed and path == "/robots.txt") or ("sitemap" in removed and path.startswith("/sitemap")):
        return True
    if "well_known" in removed and path.startswith("/.well-known/"):
        return True
    if "api" in removed and (path == "/api" or path.startswith("/api/")):
        return True
    if "openapi" in removed and path.startswith("/api/docs"):
        return True
    page = not path.startswith(("/api", "/static", "/.well-known"))
    if "alternates" in removed and page and path.endswith(SUFFIXES):
        return True
    return "markdown" in removed and path.endswith(".md")


def accepted(path: str, accept: str | None, removed: set[str]) -> str | None:
    """Return the Accept header that is sent: without the formats a condition removes."""
    if accept is None:
        return None
    if "alternates" in removed and not path.startswith("/api"):
        return "text/html"
    if "markdown" in removed:
        kept = [part for part in accept.split(",") if "markdown" not in part]
        return ",".join(kept) or "text/html"
    return accept


def shown(body: str, media: str, removed: set[str]) -> str:
    """Return a body without the parts a condition removes from the HTML pages."""
    if "html" not in media:
        return body
    if "jsonld_embed" in removed:
        body = re.sub(r'<script[^>]*type="application/ld\+json"[^>]*>.*?</script>', "", body, flags=re.S)
    if "agent_line" in removed:
        body = re.sub(r'<p[^>]*id="agents".*?</p>', "", body, flags=re.S)
    if "alternates" in removed or "markdown" in removed:
        body = re.sub(r'<link[^>]*rel="(alternate|describedby)"[^>]*>', "", body)
    if "api" in removed:
        body = re.sub(r'<a[^>]*href="[^"]*/api/[^"]*"[^>]*>.*?</a>', "", body, flags=re.S)
    return body


class Platform:
    """The tools of one run of the agent, on the copy of the platform at site, under a condition."""

    def __init__(self, site: str, base: str, condition: dict, client_ip: str, http: httpx.AsyncClient):
        self.site, self.base, self.removed, self.http = site.rstrip("/"), base, condition["removed"], http
        self.headers = {"User-Agent": "agent-ready-eval", "X-Forwarded-For": client_ip}
        self.calls: list[dict] = []

    def local(self, url: str) -> str | None:
        """Return the address on the copy of a platform address, or None for another site."""
        address = urljoin(self.base, url.strip())
        if not address.startswith(self.base.rstrip("/")):
            return None
        return self.site + address[len(self.base.rstrip("/")):]

    async def get(self, url: str, accept: str | None) -> tuple[int, dict, str, str]:
        """Return the status, headers, body and final address of a GET, as the condition serves it."""
        address = self.local(url)
        if address is None:
            return 0, {}, f"Only addresses on {self.base} can be reached.", url
        path = urlparse(address).path
        if blocked(path, self.removed):
            return 404, {"Content-Type": "text/html"}, "<h1>404 Not Found</h1>", url
        headers = dict(self.headers)
        if accepted(path, accept, self.removed):
            headers["Accept"] = accepted(path, accept, self.removed)
        answer = await self.http.get(address, headers=headers, follow_redirects=True, timeout=60)
        final = str(answer.url).replace(self.site, self.base.rstrip("/"), 1)
        if blocked(urlparse(str(answer.url)).path, self.removed):
            return 404, {"Content-Type": "text/html"}, "<h1>404 Not Found</h1>", final
        kept = {name: answer.headers[name].replace(self.site + "/", self.base) for name in ("Content-Type", "X-Pagination", "Link") if name in answer.headers}
        if "link_header" in self.removed:
            kept.pop("Link", None)
        body = answer.text.replace(self.site + "/", self.base)
        return answer.status_code, kept, shown(body, kept.get("Content-Type", ""), self.removed), final

    async def fetch(self, url: str, accept: str | None = None, offset: int = 0) -> tuple[str, bool]:
        status, headers, body, final = await self.get(url, accept)
        self.calls.append({"tool": "fetch", "url": final, "accept": accept, "status": status, "chars": len(body)})
        lines = [f"HTTP {status}", *(f"{name}: {value}" for name, value in headers.items())]
        if final != urljoin(self.base, url):
            lines.append(f"Final address: {final}")
        part = body[offset:offset + CHUNK]
        note = f"\n\n[Characters {offset}-{offset + len(part)} of {len(body)}. Call fetch with offset={offset + CHUNK} to read more.]" \
            if len(body) > offset + CHUNK or offset else ""
        return "\n".join(lines) + "\n\n" + part + note, status == 0 or status >= 400

    async def web_fetch(self, url: str, prompt: str, client: anthropic.AsyncAnthropic, usage: list) -> tuple[str, bool]:
        """Fetch like Claude Code: the page in Markdown (scripts dropped), read by a small model for the prompt."""
        status, headers, body, final = await self.get(url, "text/html,application/xhtml+xml,*/*;q=0.8")
        self.calls.append({"tool": "web_fetch", "url": final, "status": status, "chars": len(body)})
        if status == 0 or status >= 400:
            return f"HTTP {status}: {body[:500]}", True
        if "html" in headers.get("Content-Type", ""):
            body = markdownify(re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S))
        message, _ = await call(client, model="claude-haiku-5-5", max_tokens=4000, messages=[{"role": "user", "content":
            f"Web page content:\n---\n{body[:100000]}\n---\n\n{prompt}\n\nAnswer concisely, from the content above only."}])
        usage.append(message.usage.model_dump())
        return "".join(block.text for block in message.content if block.type == "text"), False


FETCH = {"name": "fetch", "description": "Send an HTTP GET request to an address on the platform and return the status, the main headers "
         "and the body as text. A long body is returned in parts of 30000 characters: call again with offset to read further.",
         "input_schema": {"type": "object", "properties": {
             "url": {"type": "string", "description": "The address, such as https://platform.vhp4safety.nl/."},
             "accept": {"type": "string", "description": "The Accept header, such as application/json. Optional."},
             "offset": {"type": "integer", "description": "The first character of the body to return. Default 0."}},
             "required": ["url"]}}
WEB_FETCH = {"name": "web_fetch", "description": "Fetch an address on the platform and answer a prompt about its content: the page is "
             "converted to Markdown and read by a small, fast model, which returns its answer to the prompt.",
             "input_schema": {"type": "object", "properties": {
                 "url": {"type": "string", "description": "The address to fetch."},
                 "prompt": {"type": "string", "description": "What to find in the content of the page."}},
                 "required": ["url", "prompt"]}}


# One run of the agent ----------------------------------------------------------------------------------------------


class Refused(Exception):
    pass


async def call(client: anthropic.AsyncAnthropic, **request):
    """Send a request, retrying rate limits, overload and connection errors with jittered backoff."""
    for attempt in range(8):
        try:
            return await client.messages.create(**request), attempt + 1
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as problem:
            failure = problem
        except anthropic.APIStatusError as problem:
            if problem.status_code < 500 and problem.status_code != 429:
                raise
            failure = problem
        await asyncio.sleep(min(60, 2 ** attempt + random.random() * 2))
    raise failure


async def run_case(args, client, http, question: dict, condition_name: str, rep: int) -> dict:
    condition, _ = CONDITIONS[condition_name]
    base = args.base
    index = list(CONDITIONS).index(condition_name)
    # Each run is its own client of the platform, with its own rate limit, as each agent would be.
    platform = Platform(args.site, base, condition, f"10.{index}.{zlib.crc32(question['id'].encode()) % 250}.{rep + 1}", http)
    tools = ([FETCH] if "fetch" in condition["tools"] else []) + ([WEB_FETCH] if "webfetch" in condition["tools"] else [])
    system = SYSTEM.format(base=base)
    messages = [{"role": "user", "content": question["question"]}]
    trace = [{"role": "system", "content": system}, {"role": "user", "content": question["question"]}]
    usage, aux, attempts, started, tool_calls, stop = [], [], 0, time.monotonic(), 0, None
    final = ""
    for turn in range(args.max_turns):
        message, tries = await call(client, model=args.model, max_tokens=16000, system=system, tools=tools, messages=messages,
                                    output_config={"effort": args.effort}, cache_control={"type": "ephemeral"})
        attempts += tries
        if not message.model.startswith(args.model):
            raise RuntimeError(f"served by {message.model}, not {args.model}")
        usage.append(message.usage.model_dump())
        messages.append({"role": "assistant", "content": message.content})
        stop = message.stop_reason
        text = "".join(block.text for block in message.content if block.type == "text")
        if text:
            trace.append({"role": "assistant", "content": text})
        if stop == "refusal":
            break
        if stop != "tool_use":
            final = text
            break
        results = []
        for block in (block for block in message.content if block.type == "tool_use"):
            tool_calls += 1
            trace.append({"role": "tool_call", "name": block.name, "content": json.dumps(block.input, indent=1)})
            inputs = block.input if isinstance(block.input, dict) else {}
            try:
                if block.name == "fetch":
                    output, failed = await platform.fetch(inputs.get("url", ""), inputs.get("accept"), int(inputs.get("offset") or 0))
                else:
                    output, failed = await platform.web_fetch(inputs.get("url", ""), inputs.get("prompt", ""), client, aux)
            except (httpx.HTTPError, ValueError) as problem:
                output, failed = f"The request failed: {problem}", True
            trace.append({"role": "tool_result", "content": output})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": failed})
        messages.append({"role": "user", "content": results})
    else:
        stop = "max_turns"
    return {"final": final, "stop": stop, "usage": usage, "aux": aux, "attempts": attempts, "tool_calls": tool_calls,
            "latency_s": round(time.monotonic() - started, 1), "trace": trace, "calls": platform.calls}


def features(calls: list[dict]) -> dict[str, int]:
    """Return which features of the platform a run used, from its tool calls."""
    used = {}
    for done in calls:
        path = urlparse(done["url"]).path
        kind = ("llms" if path.startswith("/llms") else "robots" if path == "/robots.txt" else "sitemap" if path.startswith("/sitemap")
                else "well_known" if path.startswith("/.well-known") else "openapi" if path.startswith("/api/docs")
                else "api_search" if path.startswith("/api/search") else "api_facets" if path.endswith("/facets")
                else "api_dump" if path.startswith("/api/dump") else "api" if path.startswith("/api")
                else "markdown" if path.endswith(".md") or "markdown" in (done.get("accept") or "")
                else "page_rdf" if path.endswith(SUFFIXES) or any(media in (done.get("accept") or "") for media in ("ld+json", "turtle", "n-triples"))
                else "page_html")
        used[kind] = used.get(kind, 0) + 1
    return used


# Storage, the harness gate and the summary ---------------------------------------------------------------------------


def harness_sha() -> str:
    digest = hashlib.sha256()
    for path in (HERE / "run.py", HERE / "questions.yaml"):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def stored(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def cost(usage: dict, model: str) -> float:
    """Return the price of one request; cache writes cost 1.25 times the input, and cache reads 0.1 times."""
    prompt = sum(usage.get(key) or 0 for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    rate_in, rate_out = LONG_PRICES.get(model, PRICES[model]) if prompt > 100000 and model in LONG_PRICES else PRICES[model]
    return (usage.get("input_tokens", 0) * rate_in + usage.get("cache_creation_input_tokens", 0) * rate_in * 1.25
            + usage.get("cache_read_input_tokens", 0) * rate_in * 0.1 + usage.get("output_tokens", 0) * rate_out) / 1e6


def total(usages: list[dict]) -> dict:
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    return {key: sum(usage.get(key) or 0 for usage in usages) for key in keys}


def interval(values: list[float], rounds: int = 2000) -> tuple[float, float]:
    """Return a 95% bootstrap interval of the mean."""
    rng = random.Random(0)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(rounds))
    return means[int(0.025 * rounds)], means[int(0.975 * rounds)]


def paired(by_case: dict, reference: dict) -> tuple[float, float, float, float, int]:
    """Return the mean per-question difference of F1 with the reference, its 95% interval and a sign-flip p-value."""
    shared = sorted(set(by_case) & set(reference))
    deltas = [statistics.fmean(by_case[case]) - statistics.fmean(reference[case]) for case in shared]
    if not deltas:
        return 0.0, 0.0, 0.0, 1.0, 0
    low, high = interval(deltas)
    observed, rng = abs(statistics.fmean(deltas)), random.Random(1)
    extreme = sum(abs(statistics.fmean([delta * rng.choice((-1, 1)) for delta in deltas])) >= observed - 1e-12 for _ in range(5000))
    return statistics.fmean(deltas), low, high, (extreme + 1) / 5001, len(deltas)


def summary(out: Path, model_filter: str | None = None) -> str:
    rows = {name: [row for row in stored(out / variant / "results.jsonl") if row.get("status") == "ok"]
            for name, variant in variants().items()}
    errors = {name: len(stored(out / variant / "errors.jsonl")) for name, variant in variants().items()}
    per_case = {name: {} for name in rows}
    for name, listed in rows.items():
        for row in listed:
            per_case[name].setdefault(row["prompt_id"], []).append(row["grade"]["f1"])
    lines = ["| condition | runs | F1 (95% CI) | one-hop F1 | multi-hop F1 | exact | answered | tool calls | cost/run | vs full: ΔF1 (95% CI), p |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, listed in rows.items():
        if not listed:
            continue
        f1 = [row["grade"]["f1"] for row in listed]
        low, high = interval(f1)
        hops = {tag: [row["grade"]["f1"] for row in listed if row["tags"][0] == tag] for tag in ("one-hop", "multi-hop")}
        spend = statistics.fmean(row["cost_usd"] for row in listed)
        versus = ""
        if name != "full" and per_case["full"]:
            mean, d_low, d_high, p, n = paired(per_case[name], per_case["full"])
            versus = f"{mean:+.2f} ({d_low:+.2f} to {d_high:+.2f}), p={p:.3f}, n={n}"
        lines.append(f"| {name} | {len(listed)}{f' (+{errors[name]} errors)' if errors[name] else ''} | {statistics.fmean(f1):.2f} ({low:.2f}-{high:.2f}) | "
                     + " | ".join(f"{statistics.fmean(values):.2f}" if values else "-" for values in hops.values())
                     + f" | {statistics.fmean(row['grade']['exact'] for row in listed):.2f} | {statistics.fmean(row['grade']['answered'] for row in listed):.2f}"
                     + f" | {statistics.fmean(row['tool_calls'] for row in listed):.1f} | ${spend:.3f} | {versus} |")
    usage = ["", "Share of runs that used each feature, per condition:", "",
             "| condition | " + " | ".join(FEATURES) + " |", "|---|" + "---|" * len(FEATURES)]
    for name, listed in rows.items():
        if listed:
            usage.append(f"| {name} | " + " | ".join(f"{sum(1 for row in listed if row['meta']['features'].get(feature)) / len(listed):.0%}" for feature in FEATURES) + " |")
    return "\n".join(lines + usage)


FEATURES = ["llms", "robots", "sitemap", "well_known", "openapi", "api_search", "api", "api_facets", "api_dump", "markdown", "page_rdf", "page_html"]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", required=True, help="The copy of the platform, such as http://localhost:5070")
    parser.add_argument("--key-file", help="A file with the Anthropic API key; else the usual credentials of the SDK")
    parser.add_argument("--conditions", default=",".join(CONDITIONS), help="Comma-separated conditions: " + ", ".join(CONDITIONS))
    parser.add_argument("--questions", default="", help="Comma-separated question ids; default all")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--model", default="claude-opus-5-5", choices=sorted(PRICES))
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--timeout-s", type=int, default=900, help="The wall-clock ceiling of one run")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", default=str(HERE.parent.parent / ".claude" / "hillclimb" / "agent-ready"))
    parser.add_argument("--summary", action="store_true", help="Only print the summary of the stored results")
    parser.add_argument("--approve-harness", action="store_true", help="Record the current runner and questions as approved")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.summary:
        print(summary(out))
        return
    state_file = out / "_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    state.update(metrics=[{"id": "f1", "label": "F1", "kind": "float", "scale": 1}, {"id": "precision", "label": "Precision", "kind": "float", "scale": 1},
                          {"id": "recall", "label": "Recall", "kind": "float", "scale": 1}, {"id": "exact", "label": "Exact set", "kind": "float", "scale": 1},
                          {"id": "answered", "label": "Answered", "kind": "float", "scale": 1}],
                 perf_fields=[{"id": "cost_usd", "label": "Cost", "unit": "$"}, {"id": "tool_calls", "label": "Tool calls"}, {"id": "latency_s", "label": "Latency", "unit": "s"}])
    if args.approve_harness:
        state["harness_sha"] = harness_sha()
    state_file.write_text(json.dumps(state, indent=1))
    if state.get("harness_sha") != harness_sha():
        raise SystemExit("run.py or questions.yaml changed since they were approved; check them, then run once with --approve-harness")
    spec = yaml.safe_load((HERE / "questions.yaml").read_text())
    args.base = spec["base"]
    async with httpx.AsyncClient() as http:
        dump = Graph().parse(data=(await http.get(args.site.rstrip("/") + "/api/dump", headers={"Accept": "application/n-triples"}, timeout=300)).text, format="nt")
        gold, named = golds(spec, dump), names(dump, args.base)
        # The description of the API is made once before the runs, as its first making takes seconds.
        await http.get(args.site.rstrip("/") + "/api/docs/openapi.json", timeout=300)
        client = anthropic.AsyncAnthropic(api_key=Path(args.key_file).expanduser().read_text().strip() if args.key_file else None, max_retries=0)
        chosen = [question for question in spec["questions"] if not args.questions or question["id"] in args.questions.split(",")]
        limit = asyncio.Semaphore(args.concurrency)
        jobs = []
        for name in args.conditions.split(","):
            variant = out / variants()[name]
            (variant / "traces").mkdir(parents=True, exist_ok=True)
            if name != "full":
                (variant / "change.md").write_text(f"# {name}\n\n{CONDITIONS[name][1]}\n")
            done = {(row["prompt_id"], row["rep"]) for row in stored(variant / "results.jsonl")}
            for rep in range(args.reps):
                for question in chosen:
                    if (question["id"], rep) not in done:
                        jobs.append((name, variant, question, rep))
        random.Random(2).shuffle(jobs)
        print(f"{len(jobs)} runs: {len(chosen)} questions, {args.reps} reps, conditions {args.conditions}, model {args.model}", flush=True)

        async def one(name, variant, question, rep):
            async with limit:
                try:
                    run = await asyncio.wait_for(run_case(args, client, http, question, name, rep), args.timeout_s)
                except Exception as problem:  # every failure of the harness or the API is recorded apart, not scored
                    kind = "timeout" if isinstance(problem, TimeoutError) else type(problem).__name__
                    with open(variant / "errors.jsonl", "a") as errors:
                        errors.write(json.dumps({"prompt_id": question["id"], "rep": rep, "class": kind, "detail": str(problem)[:500]}) + "\n")
                    print(f"ERROR {name} {question['id']} rep {rep}: {kind} {str(problem)[:200]}", flush=True)
                    return
                grade = graded(answered(run["final"]), gold[question["id"]], args.base, args.site, named)
                given = grade.pop("_given")
                usage = total(run["usage"])
                row = {"prompt_id": question["id"], "prompt": question["question"], "tags": question["tags"], "rep": rep, "condition": name,
                       "model": args.model, "stop_reason": run["stop"], "status": "truncated" if run["stop"] == "max_tokens" else "ok",
                       "grade": grade, "latency_s": run["latency_s"], "tool_calls": run["tool_calls"], "usage": usage,
                       "in_tokens": usage["input_tokens"] + usage["cache_read_input_tokens"] + usage["cache_creation_input_tokens"],
                       "out_tokens": usage["output_tokens"], "aux_usage": total(run["aux"]), "attempts": run["attempts"],
                       "cost_usd": round(sum(cost(one, args.model) for one in run["usage"]) + sum(cost(one, "claude-haiku-5-5") for one in run["aux"]), 4),
                       "meta": {"features": features(run["calls"]), "given": given, "gold": sorted(gold[question["id"]]),
                                "missing": sorted(gold[question["id"]] - set(given)), "extra": sorted(set(given) - gold[question["id"]])}}
                (variant / "traces" / f"{question['id']}_rep{rep}.json").write_text(json.dumps(run["trace"], indent=1))
                with open(variant / "results.jsonl", "a") as results:
                    results.write(json.dumps(row) + "\n")
                print(f"{name:16} {question['id']:38} rep {rep}  F1 {grade['f1']:.2f}  calls {run['tool_calls']:2}  ${row['cost_usd']:.3f}  {run['stop']}", flush=True)

        await asyncio.gather(*(one(*job) for job in jobs))
    print(summary(out))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
