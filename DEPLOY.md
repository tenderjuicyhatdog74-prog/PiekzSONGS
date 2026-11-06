# Publish Plum on Render

The website requires a Python web service, not static-only hosting: the server powers the internet search for song meanings. Render provides a public HTTPS link.

1. Create a GitHub account if you don't already have one: https://github.com/signup
2. Make a new GitHub repository. Upload these files to the root of the repository: `index.html`, `server.py`, `render.yaml` and `README.md`. (On GitHub: **Add file → Upload files → Commit changes**.)
3. Create or sign in to a Render account at https://dashboard.render.com/ and connect it to your GitHub account.
4. Choose **New → Web Service**, select your repository and use these settings:
   - Language/runtime: Python 3
   - Build command: `python -m compileall -q server.py`
   - Start command: `python server.py`
   - Instance type: Free (if available)
5. Click **Create Web Service**. Once deployment finishes, Render provides your public `onrender.com` website link.

The included `render.yaml` can alternatively be used with Render's Blueprint feature. The site works without API keys for the song search and web-search excerpts. Online services or search engines may rate-limit or block requests. Free services may sleep when idle and take time to wake up. Lyrics and background information are not guaranteed for all songs.

## Optional: enable Genius

To try Genius first, add the environment variable `GENIUS_ACCESS_TOKEN` in the Render service dashboard using your own Genius API client access token. Never commit the token to GitHub or put it in `index.html`. Without one, Plum searches the web and then Wikipedia. Get a token at https://genius.com/api-clients.

Local testing: run `python3 server.py`, then open http://localhost:8000.
