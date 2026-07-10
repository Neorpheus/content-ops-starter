import urllib.request
import urllib.parse
import re

def test_ddg_search(query_str):
    encoded_query = urllib.parse.quote(query_str)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            
            # Find links and titles
            # Structure in DDG HTML:
            # <a class="result__a" href="//duckduckgo.com/l/?uddg=http%3A%2F%2F...&amp;rut=...">Title of Result</a>
            
            # 1. Find all result link anchors
            # We match class="result__a" and its href
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            results = []
            for link, title in matches:
                # Clean title (remove HTML tags)
                title = re.sub(r'<[^>]+>', '', title).strip()
                
                # Decode link
                if 'uddg=' in link:
                    raw_url = link.split('uddg=')[1].split('&')[0]
                    decoded_url = urllib.parse.unquote(raw_url)
                else:
                    decoded_url = link
                    
                # Skip DDG internal links
                if not decoded_url.startswith('http'):
                    continue
                    
                results.append({"title": title, "link": decoded_url})
                if len(results) >= 3:
                    break
                    
            print(f"[+] Found {len(results)} results:")
            for idx, r in enumerate(results):
                print(f"  {idx+1}. {r['title']}")
                print(f"     Link: {r['link']}")
            return results
    except Exception as e:
        print(f"[-] Search failed: {e}")
        return []

if __name__ == '__main__':
    test_ddg_search("Medtronic Advisa pacemaker MRI safety")
