# Plum — song discovery

Plum searches the web for song interpretations and displays short excerpts with links to their sources. This is a real web lookup, not a generated AI overview. If results aren't available it checks Wikipedia instead. Search engines may block or rate-limit requests, so no source is guaranteed to work for every song. The site still lets you open a search in Google or Genius.

## Start the website

In this folder, run `python3 server.py` (or `python server.py` on Windows), then visit http://localhost:8000. The web search needs this server; opening index.html directly will not perform it.

## Optional: Genius first

Genius requires an API client access token. Create a client at https://genius.com/api-clients (documentation: https://docs.genius.com/). Set `GENIUS_ACCESS_TOKEN` in the server environment before running `server.py`:

```sh
export GENIUS_ACCESS_TOKEN='your-token-here'
python3 server.py
```

In Windows PowerShell use `$env:GENIUS_ACCESS_TOKEN='your-token-here'`, then `python server.py`. Never share or embed your token in HTML. The server keeps the token in its environment; it is not sent to the browser. When configured, Plum tries Genius first, then web search and Wikipedia. Descriptions and annotations may be unavailable or reflect a contributor's interpretation.
