#!/usr/bin/env python3
"""
OpenATS 1-Click Desktop & Web Launcher.
Starts the local server and opens your default browser.
Author: Nazmul (@3447nazmul) - https://github.com/3447nazmul/openats
"""
import os
import sys
import webbrowser
import threading
import time
from openats.server import run_server

def open_browser(url: str):
    time.sleep(1.0)
    print(f"Opening {url} in your browser...")
    webbrowser.open(url)

if __name__ == "__main__":
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "127.0.0.1")
    url = f"http://{host}:{port}"
    
    # Launch browser on background thread
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    # Run the server
    run_server(host=host, port=port)
