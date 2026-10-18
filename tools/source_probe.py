"""Small, transparent source-feasibility probe; not the production scraper."""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = 'ZylabsAssignmentResearch/0.1 (small educational news pipeline pilot)'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('urls', nargs='+')
    args = parser.parse_args()
    root = Path('research/source_probe')
    root.mkdir(parents=True, exist_ok=True)
    for url in args.urls:
        entry = {'url': url, 'checked_at': datetime.now(timezone.utc).isoformat(), 'user_agent': UA}
        try:
            request = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                entry.update(status=response.status, final_url=response.url, content_type=response.headers.get('Content-Type'), bytes=len(body))
                name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.bin'
                (root / name).write_bytes(body)
                entry['saved_path'] = str(root / name)
                print(json.dumps(entry))
                if url.endswith('/robots.txt'):
                    print(body.decode('utf-8', errors='replace')[:22000])
        except Exception as error:
            entry['error'] = str(error)
            print(json.dumps(entry))
        with (root / 'manifest.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry) + '\n')
        time.sleep(6)

if __name__ == '__main__':
    main()
