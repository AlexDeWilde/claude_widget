# Claude Usage Desktop Widget

## Overview
A custom, secure bridge solution designed to display Claude AI session limits and usage stats permanently on your desktop, without triggering generic anti-bot protections. 

## Structure
The project is split into two independent parts:
1. **Chrome Extension Bridge (`chrome_extension/`)**: 
   A lightweight, manifest v3 extension running strictly on `https://claude.ai/settings/usage`. 
   - Uses `content.js` to securely poll and scrape usage data from the user's authenticated DOM precisely every 10 seconds.
   - Pushes this data to a local Python background server. 
   - By running within an active, human-logged-in browser session, it bypasses complex external scraping challenges or bot captchas.
2. **Desktop Widget (`desktop_widget/`)**: 
   A frameless, always-on-top Python Tkinter widget.
   - Visually designed with a specialized 7-segment digital font (`DSEG7Classic-Bold.ttf`) displaying the usage percentage, limit timers, and an auto-refresh sync indicator. 
   - Runs a local `BaseHTTPRequestHandler` continuously in the background to receive updates sent from the extension.
   - Launched silently using `Launch.bat`.

## For Future Assistants / Development
1. **Network**: They talk over `http://127.0.0.1:8765/update` (POST) and `/poll` (GET). If network ports are restricted or occupied, sync them across `app.py` and `background.js`.
2. **UI Safety**: Updates loop via `self.after()` and cross-thread operations are managed safely so the GUI never hangs. 
3. **Resiliency**: The python UI assumes the state is stale if updates stop arriving, meaning it relies heavily on the Chrome extension successfully identifying DOM elements on the Claude limits page. Any breakages are highly likely due to Claude updating their CSS class names or DOM structure inside the browser.
