import requests
import json
import time
import argparse
import sys
import os
from queue import Queue
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: 'beautifulsoup4' and 'lxml' libraries are required.", file=sys.stderr)
    print("Please install them by running: pip install beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)

# ==============================================================================
# SCRIPT CONFIGURATION
# ==============================================================================
DATA_PATH_ID = "hYu0sooceSMFj4KfRbxdU"
BASE_URL = "https://filecr.com"
NEXT_DATA_URL = f"{BASE_URL}/_next/data/{DATA_PATH_ID}"
DOWNLOAD_API_URL = f"{BASE_URL}/api/actions/downloadlink/"
LOG_FILE = "log.txt"

# --- CHAMELEON MODE: A pool of different, realistic browser identities ---
HEADER_LIST = [
    # Identity 1: Chrome on Windows
    {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': f'{BASE_URL}/',
        'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    },
    # Identity 2: Firefox on Windows
    {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': f'{BASE_URL}/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    },
    # Identity 3: Edge on Windows
    {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Referer': f'{BASE_URL}/',
        'Sec-Ch-Ua': '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0',
    },
]

APP_CATEGORIES = ["tools-utilities-apps", "productivity", "news-weather", "fitness-health", "antivirus-security", "wireless-network-tools", "educational-apps", "audio-video-players", "photography", "entertainment", "maps-gps", "communication", "video-editing-apps", "mobile-browsers"]
GAME_CATEGORIES = ["action-games", "adventure-games", "casual-games", "indie-games", "racing-games", "role-playing", "sports-games", "strategy-games", "card-games", "simulation-game", "arcade-games", "puzzle-games", "board-games", "music", "educational-games"]

LOG_LOCK = Lock()

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def log_failed_url(url):
    with LOG_LOCK:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{url}\n")
        except IOError as e:
            print(f"CRITICAL: Could not write to log file {LOG_FILE}: {e}", file=sys.stderr)

def _try_html_fallback(session, api_url):
    try:
        base_api_url = api_url.split('?')[0]
        html_url = base_api_url.replace(f"{NEXT_DATA_URL}/", f"{BASE_URL}/").replace(".json", "")
        print(f"      Attempting HTML fallback: {html_url}", file=sys.stderr)
        
        html_headers = session.headers.copy()
        html_headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })
        
        response = session.get(html_url, headers=html_headers, timeout=45)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if script_tag and script_tag.string: return json.loads(script_tag.string)
        else: print("      HTML fallback failed: '__NEXT_DATA__' script tag not found.", file=sys.stderr)
    except Exception as e:
        error_msg = f"{type(e).__name__}"
        if hasattr(e, 'response') and e.response: error_msg += f" (Status: {e.response.status_code})"
        print(f"      HTML fallback failed with error: {error_msg}", file=sys.stderr)
    return None

def get_json_response(url, retries=10, backoff_factor=1, is_slug_url=False):
    with requests.Session() as s:
        header_index = 0
        s.headers.update(HEADER_LIST[header_index])
        current_url = url

        for attempt in range(retries):
            try:
                response = s.get(current_url, timeout=30, allow_redirects=False)

                if is_slug_url and response.is_redirect:
                    location = response.headers.get('Location')
                    if location:
                        parsed_loc = urlparse(location)
                        query_params = parse_qs(parsed_loc.query)
                        post_id = query_params.get('id', [None])[0]
                        if post_id:
                            new_url = f"{url.split('?')[0]}?id={post_id}"
                            if new_url != current_url:
                                print(f"      Found ID '{post_id}'. Retrying with new URL...", file=sys.stderr)
                                current_url = new_url
                            raise requests.exceptions.RetryError("Redirect with ID found, retrying.")

                response.raise_for_status()
                return response.json()
                
            except (requests.exceptions.RequestException, json.JSONDecodeError, requests.exceptions.RetryError) as e:
                error_msg = f"{type(e).__name__}"
                is_blocking_error = False
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f" (Status: {e.response.status_code})"
                    if e.response.status_code in [403, 404]:
                        is_blocking_error = True
                
                if not isinstance(e, requests.exceptions.RetryError):
                    print(f"Warning: Attempt {attempt + 1}/{retries} failed for {current_url}: {error_msg}", file=sys.stderr)
                
                # --- REACTIVE HEADER ROTATION LOGIC ---
                if is_blocking_error and len(HEADER_LIST) > 1:
                    header_index = (header_index + 1) % len(HEADER_LIST)
                    new_identity = HEADER_LIST[header_index]['User-Agent'].split(' ')[0].split('/')[0]
                    print(f"      Blocking error detected. Rotating identity to: {new_identity}", file=sys.stderr)
                    s.headers.update(HEADER_LIST[header_index])

                if attempt + 1 < retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    print(f"         Retrying in {sleep_time:.1f} seconds...", file=sys.stderr)
                    time.sleep(sleep_time)
                else:
                    if is_slug_url:
                        print(f"      All API attempts failed. Trying final HTML fallback.", file=sys.stderr)
                        fallback_data = _try_html_fallback(s, current_url)
                        if fallback_data:
                            print("      SUCCESS: Extracted data from HTML fallback.", file=sys.stderr)
                            return fallback_data
                    print(f"Error: All attempts failed for the original URL {url}. Logging it.", file=sys.stderr)
                    log_failed_url(url)
    return None

def save_json_file(data, folder, filename):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error writing to file {filepath}: {e}", file=sys.stderr)

# ==============================================================================
# CONCURRENT DOWNLOADER LOGIC
# ==============================================================================
class DownloadWorker(Thread):
    def __init__(self, queue, retries):
        Thread.__init__(self)
        self.queue = queue
        self.retries = retries

    def run(self):
        while True:
            task = self.queue.get()
            if task is None: break
            url, folder, filename, task_type = task
            print(f"--> Worker fetching ({task_type}): {filename}")
            is_slug = (task_type == "slug")
            json_data = get_json_response(url, retries=self.retries, is_slug_url=is_slug)
            if json_data:
                save_json_file(json_data, folder, filename)
            self.queue.task_done()

def start_workers(num_workers, retries):
    q = Queue()
    threads = []
    for _ in range(num_workers):
        worker = DownloadWorker(q, retries)
        worker.daemon = True
        worker.start()
        threads.append(worker)
    return q, threads

def stop_workers(q, threads):
    for _ in threads: q.put(None)
    for t in threads: t.join()

# ==============================================================================
# CORE LOGIC FUNCTIONS
# ==============================================================================
def fetch_and_process_links(slug_data, num_workers, retries):
    post = slug_data.get('props', {}).get('pageProps', {}).get('post') or slug_data.get('pageProps', {}).get('post')
    if not post: return
    downloads = post.get('downloads') or slug_data.get('props',{}).get('pageProps',{}).get('downloads',[])
    if not downloads: return
    print(f"    --fetch-links active. Found {len(downloads)} versions...")
    link_ids = [link.get('id') for v in downloads for link in v.get('links',[]) if link.get('id')]
    if not link_ids: return print("    No link IDs found.")
    q, threads = start_workers(num_workers, retries)
    for link_id in link_ids:
        q.put((f"{DOWNLOAD_API_URL}?id={link_id}", 'downloadlink', f"{link_id}.json", "link"))
    q.join(); stop_workers(q, threads)
    print(f"    Finished fetching all {len(link_ids)} link files.")

def fetch_all_slugs_concurrently(page_data, base_path, slug_subfolder, num_workers, fetch_links, retries):
    print(f"\n--fetch-slugs active. Starting {num_workers} workers...")
    posts = page_data.get('pageProps', {}).get('posts', [])
    if not posts: return print("Warning: No 'posts' found to process.", file=sys.stderr)
    q, threads = start_workers(num_workers, retries)
    slug_path = os.path.join(base_path, slug_subfolder)
    tasks = [(f"{NEXT_DATA_URL}/{base_path}/{p.get('slug')}.json", slug_path, f"{p.get('slug')}.json", "slug") for p in posts if p.get('slug')]
    for task in tasks: q.put(task)
    q.join(); stop_workers(q, threads)
    print(f"\nFinished fetching slug files.")
    if fetch_links:
        for i, task_info in enumerate(tasks):
            filepath = os.path.join(task_info[1], task_info[2])
            try:
                with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
                print(f"\n({i+1}/{len(tasks)}) Processing links inside: {task_info[2]}")
                fetch_and_process_links(data, num_workers, retries)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Warning: Could not process {filepath}. {e}", file=sys.stderr)

def process_paginated_download(base_path, slug_subfolder, url_path, fetch_slugs, fetch_links, workers, retries):
    page_num, next_cursor = 1, None
    while True:
        print("\n" + "#"*25 + f" STARTING PAGE {page_num} " + "#"*25)
        page_save_path = os.path.join(url_path, 'page')
        url = f"{NEXT_DATA_URL}/{url_path}.json" + (f"?c={next_cursor}" if next_cursor else "")
        page_data = get_json_response(url, retries=retries)
        if not page_data or not page_data.get('pageProps', {}).get('posts'):
            print(f"No more posts found. Concluding.")
            break
        save_json_file(page_data, page_save_path, f"page{page_num}.json")
        if fetch_slugs:
            fetch_all_slugs_concurrently(page_data, base_path, slug_subfolder, workers, fetch_links, retries)
        next_cursor = page_data.get('pageProps', {}).get('meta', {}).get('next_cursor')
        if not next_cursor:
            print("Reached the final page. Concluding.")
            break
        page_num += 1; time.sleep(1)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Ultimate downloader for FileCR.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('category', choices=['apps', 'games'], help="The base category.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--page', type=int, help="Download one specific page.")
    mode.add_argument('--all-pages', action='store_true', help="Download ALL pages.")
    mode.add_argument('--category-slug', type=str, help="Download ALL pages for a specific sub-category.")
    parser.add_argument('--fetch-slugs', action='store_true', help="LEVEL 2: Also download item details.")
    parser.add_argument('--fetch-links', action='store_true', help="LEVEL 3: Also download final link details.")
    parser.add_argument('--workers', type=int, default=10, help="Concurrent downloads (default: 10).")
    parser.add_argument('--retries', type=int, default=5, help="Retry attempts per download (default: 10).")
    args = parser.parse_args()
    if args.fetch_links and not args.fetch_slugs:
        parser.error("--fetch-links requires --fetch-slugs.")
    print(f"[*] Failed downloads will be logged to: {os.path.abspath(LOG_FILE)}")
    base_path = "android" if args.category == 'apps' else "android-games"
    slug_subfolder = "apps" if args.category == 'apps' else "games"
    if args.category_slug:
        valid_cats = APP_CATEGORIES if args.category == 'apps' else GAME_CATEGORIES
        if args.category_slug not in valid_cats: parser.error(f"'{args.category_slug}' is not a valid slug.")
        prefix = "apps" if args.category == 'apps' else ""
        url_path = os.path.join(base_path, prefix, args.category_slug).replace("\\", "/")
        process_paginated_download(base_path, slug_subfolder, url_path, args.fetch_slugs, args.fetch_links, args.workers, args.retries)
    elif args.all_pages:
        process_paginated_download(base_path, slug_subfolder, base_path, args.fetch_slugs, args.fetch_links, args.workers, args.retries)
    elif args.page:
        page_save_path = os.path.join(base_path, 'page')
        url_to_fetch, next_cursor = f"{NEXT_DATA_URL}/{base_path}.json", None
        if args.page > 1:
            for _ in range(1, args.page):
                nav_url = url_to_fetch + (f"?c={next_cursor}" if next_cursor else "")
                data = get_json_response(nav_url, retries=args.retries)
                if not data: return print(f"Error: Failed to navigate to page {args.page}.", file=sys.stderr)
                next_cursor = data.get('pageProps',{}).get('meta',{}).get('next_cursor')
                if not next_cursor: return print(f"Error: Reached end before page {args.page}.", file=sys.stderr)
                time.sleep(0.5)
            url_to_fetch += f"?c={next_cursor}"
        page_data = get_json_response(url_to_fetch, retries=args.retries)
        if page_data:
            save_json_file(page_data, page_save_path, f"page{args.page}.json")
            if args.fetch_slugs:
                fetch_all_slugs_concurrently(page_data, base_path, slug_subfolder, args.workers, args.fetch_links, args.retries)

if __name__ == "__main__":
    main()
