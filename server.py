#!/usr/bin/env python3
"""Serve Plum and optionally look up song commentary through the official Genius API."""
import json, os, re, unicodedata, subprocess
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TOKEN = os.environ.get('GENIUS_ACCESS_TOKEN', '').strip()
PORT = int(os.environ.get('PORT', '8000'))

def normalize(s):
    s = unicodedata.normalize('NFKD', s.lower())
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def get_api(path, params):
    req = Request('https://api.genius.com' + path + '?' + urlencode(params), headers={'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'PlumMusicDiscovery/1.0', 'Accept': 'application/json'})
    with urlopen(req, timeout=8) as response:
        return json.load(response).get('response', {})

def lookup(title, artist):
    if not TOKEN:
        return {'status': 'not_configured'}
    hits = get_api('/search', {'q': title + ' ' + artist}).get('hits', [])
    nt = normalize(title)
    artist_words = [x for x in normalize(artist).split() if len(x) > 2 and x not in ('the', 'and', 'feat', 'with')]
    def matches(song):
        st = normalize(song.get('title', ''))
        sa = normalize(song.get('artist_names', '') + ' ' + song.get('primary_artist', {}).get('name', ''))
        return (st == nt or st.startswith(nt + ' ') or nt.startswith(st + ' ')) and (not artist_words or any(x in sa for x in artist_words))
    song = next((h.get('result', {}) for h in hits if h.get('type') == 'song' and matches(h.get('result', {}))), None)
    if not song:
        return {'status': 'not_found'}
    sid = song['id']
    url = song.get('url', '')
    if not url.startswith('https://genius.com/'):
        url = 'https://genius.com/search?' + urlencode({'q': title + ' ' + artist})
    detail = get_api('/songs/' + str(sid), {'text_format': 'plain'}).get('song', {})
    desc = (detail.get('description') or {}).get('plain', '') or ''
    # An About section can be empty or say only "?". Don't invent a song meaning.
    if len(desc.strip()) > 45:
        return {'status': 'ok', 'kind': 'Song description', 'text': desc.strip(), 'url': url}
    refs = get_api('/referents', {'song_id': sid, 'text_format': 'plain', 'per_page': 10}).get('referents', [])
    for ref in refs:
        for ann in ref.get('annotations', []):
            body = (ann.get('body') or {}).get('plain', '') or ''
            if len(body.strip()) > 45:
                return {'status': 'ok', 'kind': 'Lyric annotation', 'text': body.strip(), 'url': url}
    return {'status': 'not_found', 'url': url}

class SearchParser(HTMLParser):
    """Extract public web-result titles, links and snippets, not arbitrary page markup."""
    def __init__(self):
        super().__init__(); self.depth=0; self.card=None; self.card_depth=None; self.capture=None; self.capture_depth=None; self.results=[]
    def handle_starttag(self, tag, attrs):
        self.depth+=1
        a=dict(attrs); classes=a.get('class','').split()
        if self.card is None and a.get('data-type')=='web':
            self.card={'title':'','snippet':'','url':''}; self.card_depth=self.depth
        if self.card is not None:
            if tag=='a' and not self.card['url'] and a.get('href','').startswith(('https://','http://')): self.card['url']=a['href']
            if self.capture is None and ('search-snippet-title' in classes or 'generic-snippet' in classes or 'video-snippet' in classes):
                self.capture='title' if 'search-snippet-title' in classes else 'snippet';self.capture_depth=self.depth
        if tag in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.depth-=1
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'): self.depth-=1
    def handle_endtag(self, tag):
        if self.capture and self.depth==self.capture_depth: self.capture=None;self.capture_depth=None
        if self.card is not None and self.depth==self.card_depth:
            self.results.append(self.card);self.card=None;self.card_depth=None
        self.depth=max(0,self.depth-1)
    def handle_data(self, data):
        if self.card is not None and self.capture:self.card[self.capture]+=' '+data

class DuckParser(HTMLParser):
    def __init__(self):
        super().__init__();self.current=None;self.capture=None;self.results=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);cls=a.get('class','').split()
        if tag=='a' and 'result-link' in cls:
            raw=a.get('href',''); href=parse_qs(urlsplit(raw).query).get('uddg',[raw])[0]
            self.current={'title':'','url':href,'snippet':''};self.capture='title'
        elif tag=='td' and 'result-snippet' in cls and self.current:self.capture='snippet'
    def handle_endtag(self,tag):
        if tag=='a' and self.capture=='title':self.capture=None
        elif tag=='td' and self.capture=='snippet':
            self.capture=None;self.results.append(self.current);self.current=None
    def handle_data(self,data):
        if self.current is not None and self.capture:self.current[self.capture]+=' '+data

def web_lookup(title, artist):
    query='"'+title+'" "'+artist+'" song meaning'
    req=Request('https://lite.duckduckgo.com/lite/?'+urlencode({'q':query}),headers={'User-Agent':'Mozilla/5.0'})
    try:
        with urlopen(req,timeout=10) as r: raw=r.read(2_000_000).decode('utf-8','replace')
        parser=DuckParser();parser.feed(raw);results=parser.results
    except (HTTPError,URLError,OSError):results=[]
    if not results:
        req=Request('https://search.brave.com/search?'+urlencode({'q':title+' '+artist+' song meaning', 'source':'web'}),headers={'User-Agent':'Mozilla/5.0'})
        with urlopen(req,timeout=10) as r:raw=r.read(2_000_000).decode('utf-8','replace')
        parser=SearchParser();parser.feed(raw);results=parser.results
    target=normalize(title);artist_words=[x for x in normalize(artist).split() if len(x)>2 and x not in ('the','and','feat','with')]
    choices=[]
    for item in results:
        name=' '.join(item['title'].split());snippet=' '.join(item['snippet'].split());url=item['url'];label=normalize(name)
        if not target or target not in label or (artist_words and not any(w in normalize(name+' '+snippet) for w in artist_words)):continue
        if len(snippet)<55 or not url.startswith(('http://','https://')):continue
        if re.search(r'\[(verse|chorus|bridge)\]|read more \[verse',snippet,re.I):continue
        score=(4 if re.search(r'meaning|interpretation|analysis|explained|breakdown',name,re.I) else 0)+(3 if re.search(r'about|explor|represent|themes? of|longing|yearning|heartbreak|connection|grief|reassurance|isolat|relationship|love',snippet,re.I) else 0)
        if score<4 or not re.search(r'about|explor|represent|themes? of|longing|yearning|heartbreak|connection|grief|reassurance|isolat|relationship|love|loss|pain|desire|vulnerab|wanting',snippet,re.I):continue
        sentences=re.split(r'(?<=[.!?])\s+',snippet)
        relevant=[x for x in sentences if re.search(r'\b(?:about|explores?|longing|yearning|heartbreak|connection|grief|reassurance|isolat\w*|relationship|love|loss|pain|desire|vulnerab\w*|wanting)\b',x,re.I)]
        if relevant: snippet=max(relevant,key=lambda x:bool(re.search(r'\b(?:about|explores?|represents?|themes? of)\b',x,re.I)))
        words=snippet.split();snippet=' '.join(words[:25])+('…' if len(words)>25 else '')
        choices.append((score,{'title':name,'url':url,'snippet':snippet}))
    choices.sort(key=lambda pair:pair[0],reverse=True)
    return {'status':'ok' if choices else 'not_found','results':[x[1] for x in choices[:3]]}

class Handler(SimpleHTTPRequestHandler):
    # Do not expose the server source, deployment files, or other workspace files.
    def do_HEAD(self):
        if urlsplit(self.path).path not in ('/', '/index.html'):
            self.send_error(404); return
        self.path = '/index.html'
        return super().do_HEAD()

    def do_GET(self):
        req = urlsplit(self.path)
        if req.path in ('/', '/index.html'):
            self.path = '/index.html'
            return super().do_GET()
        if req.path not in ('/api/genius', '/api/web-meaning'):
            self.send_error(404); return
        args = parse_qs(req.query)
        title, artist = (args.get(k, [''])[0][:200].strip() for k in ('title', 'artist'))
        try:
            result = (lookup(title, artist) if req.path == '/api/genius' else web_lookup(title, artist)) if title and artist else {'status': 'bad_request'}
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError, subprocess.SubprocessError):
            result = {'status': 'unavailable'}
        raw = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

if __name__ == '__main__':
    print('Plum is running on port', PORT, '| Genius API:', 'configured' if TOKEN else 'not configured', flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
