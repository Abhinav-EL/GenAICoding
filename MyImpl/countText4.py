"""
***** FIRST Prompt -- As an SRE looking to run safe, performant & maintainable code -- what improvements would you suggest 
to the following code?

ANSWER: 
"Below is a production-minded rewrite of your script with SRE improvements for safety, performance, and maintainability. 
Key changes and rationale are summarized after the code.

Improvements included

Use ThreadPoolExecutor (network I/O is I/O-bound — threads are more efficient than processes).
Per-thread requests.Session to reuse connections and reduce overhead (thread-local session).
Retries with backoff using urllib3.util.retry.Retry and requests' HTTPAdapter.
Connection & read timeouts and streaming read with a hard content-size cap to avoid OOM.
Deterministic tokenization via a compiled regex; configurable behavior.
Incremental merging of Counter results as futures complete to limit memory spikes.
Proper logging (no print), structured warnings on failures and metrics (counts).
Graceful handling of KeyboardInterrupt and cancellation of pending tasks.
Configurable max workers and sensible defaults.
Clear docstrings and typed signatures for maintainability."

ADDITIONAL CONTEXT:
Notes, trade-offs, and further SRE considerations

Why ThreadPoolExecutor not ProcessPoolExecutor?
-Network downloads are I/O-bound; threads are cheaper and reuse OS-level connection pools. Processes impose heavier memory 
and startup overhead.
-If counting becomes a bottleneck (very large texts or heavy CPU parsing), consider a hybrid: I/O with threads, then hand off 
heavier CPU work to a ProcessPoolExecutor (or use multiprocessing for just counting).

Connection reuse: thread-local requests.Session lets each worker reuse TCP connections (connection pooling), reducing latency 
and system load.

Retries & backoff: Retry configuration helps transient network issues; tune MAX_RETRIES and BACKOFF_FACTOR to your 
environment.

Timeouts and size limits: Protects service from hanging requests and extremely large responses.

Backpressure & rate limiting: This implementation does not globally rate-limit outbound requests — if you call many URLs 
or share network bandwidth, add rate limiting (e.g., token bucket) or restrict max_workers.

Observability: we log key events. For production, emit metrics (requests, failures, bytes downloaded, durations) to your 
monitoring stack.

Security: you may wish to validate or canonicalize URLs, restrict to allowed domains, and respect robots.txt if crawling 
external sites.

Encoding and tokenization: we decode using resp.encoding with errors='replace' and tokenizes using a simple regex. For 
multi-language or more accurate tokenization use a tokenizer (spaCy, nltk) or refine the regex.

Determinism: we de-duplicate input URLs to avoid duplicate work. If duplicates should be counted multiple times, remove 
the dedupe step.

"""

import logging
import math
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

# --- Configuration ----------------------------------------------------------
MAX_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB: avoid downloading enormous files
REQUEST_TIMEOUT = (5, 15)  # (connect timeout, read timeout) seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5
USER_AGENT = "safe-count-bot/1.0 (+https://example.com)"
DEFAULT_MAX_WORKERS = 16

# keep tokenization simple and deterministic: words = letters, digits, underscore
WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)

# --- Logging ----------------------------------------------------------------
logger = logging.getLogger("wordcount")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

# --- Thread-local session factory -------------------------------------------
_thread_local = threading.local()


def _make_session() -> requests.Session:
    """Create a requests.Session configured with a retrying HTTPAdapter."""
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_thread_session() -> requests.Session:
    """Return a per-thread Session (created once per thread)."""
    if getattr(_thread_local, "session", None) is None:
        _thread_local.session = _make_session()
    return _thread_local.session


# --- Worker logic -----------------------------------------------------------
def download_and_count(url: str, *, token_pattern: re.Pattern = WORD_RE) -> Counter:
    """
    Download the URL and count word tokens in the response body.
    Returns Counter of tokens (lowercased).

    This function is safe to call concurrently from multiple threads.
    """
    session = get_thread_session()
    try:
        # Stream response so we can limit the total bytes read
        with session.get(url, timeout=REQUEST_TIMEOUT, stream=True) as resp:
            # Raise for HTTP error codes that indicate failure
            resp.raise_for_status()

            chunks: List[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_CONTENT_BYTES:
                    # defensive: abort if content too large
                    logger.warning("Truncating download (exceeded %d bytes) for %s", MAX_CONTENT_BYTES, url)
                    break
                chunks.append(chunk)

            raw = b"".join(chunks)
            # decode using response-specified encoding if present; otherwise fallback to utf-8
            encoding = resp.encoding or "utf-8"
            try:
                text = raw.decode(encoding, errors="replace")
            except Exception:
                # fallback safe decode
                text = raw.decode("utf-8", errors="replace")

            # Tokenize: the caller can change token_pattern if desired
            tokens = token_pattern.findall(text.lower())
            return Counter(tokens)

    except requests.RequestException as exc:
        logger.warning("Network error for %s: %s", url, exc)
        return Counter()
    except Exception as exc:
        logger.exception("Unexpected error processing %s: %s", url, exc)
        return Counter()


# --- Aggregation / orchestration --------------------------------------------
def aggregate_counts_from_urls(
    urls: Iterable[str],
    *,
    max_workers: Optional[int] = None,
) -> Counter:
    """
    Download and count words for the provided URLs using a thread pool, returning the merged Counter.

    - The function processes results incrementally (as futures complete) to limit peak memory usage.
    - If KeyboardInterrupt is received, it attempts a graceful shutdown and returns partial results.
    """
    if max_workers is None:
        # For IO-bound tasks, allow higher concurrency but cap it
        max_workers = min(DEFAULT_MAX_WORKERS, (len(list(urls)) or 1) * 5)

    total_counter: Counter = Counter()
    urls_list = list(dict.fromkeys(urls))  # dedupe while preserving order

    logger.info("Starting processing of %d URLs with %d workers", len(urls_list), max_workers)

    # Submit all tasks and merge counters as they complete
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_and_count, url): url for url in urls_list}
        try:
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    counter = future.result()
                except Exception as exc:
                    logger.exception("Task failed for %s: %s", url, exc)
                    continue
                # Merge incrementally to keep memory usage bounded
                total_counter.update(counter)
        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt received; cancelling outstanding tasks...")
            for fut in future_to_url:
                fut.cancel()
            # Let ThreadPoolExecutor context manager clean up workers
            # Return partial results
            return total_counter

    logger.info("Completed processing; unique tokens=%d", len(total_counter))
    return total_counter


# --- Example usage / simple test -------------------------------------------
if __name__ == "__main__":
    sample_urls = [
        "http://example.com/",
        # add more URLs to test
    ]
    counts = aggregate_counts_from_urls(sample_urls, max_workers=8)
    # print top 30 tokens
    for token, freq in counts.most_common(30):
        print(f"{token}: {freq}")
