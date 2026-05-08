import tkinter as tk
import threading
import json
import os
import sys
import time
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

def get_config_path():
    """Return path for the writable config file, always next to the exe (or script in dev)."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "widget_config.json")

# Configuration
AUTO_REFRESH_MINUTES = 10 # Triggers randomly within 17 seconds after this many minutes

# Global state
state = {
    "percentage": "--",
    "time_left": "--:--",
    "needs_refresh": True, # Start as True so it auto-fetches immediately when opened
    "auto_refresh": False, # True only when refresh was triggered automatically
    "last_update_ts": time.time(),
    "next_refresh_ts": time.time() + (AUTO_REFRESH_MINUTES * 60),
    "last_error": ""
}

# The Tkinter application class
class ClaudeWidget(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Claude Widget")
        self.overrideredirect(True) # Frameless window
        self.attributes("-topmost", True) # Always on top
        self.configure(bg="black")
        
        self.font = ("Arial", 16, "bold")
        self.btn_font = ("Arial", 16, "bold")
        self.fg_color = "#FF0000" # Bright red for stats
        
        self.btn_active = "#00FF00" # Bright Green
        self.btn_dim = "#006600" # Dim Green
        
        # UI Elements
        self.container = tk.Frame(self, bg="black", padx=10, pady=5)
        self.container.pack()

        # Percentage
        self.lbl_pct = tk.Label(self.container, text=f"{state['percentage']}%", bg="black", fg=self.fg_color, font=self.font)
        self.lbl_pct.pack(side=tk.LEFT)
        
        tk.Label(self.container, text="  ", bg="black", fg=self.fg_color, font=self.font).pack(side=tk.LEFT)
        
        # Time Left
        self.lbl_time = tk.Label(self.container, text=f"{state['time_left']}", bg="black", fg=self.fg_color, font=self.font)
        self.lbl_time.pack(side=tk.LEFT)
        
        tk.Label(self.container, text="  ", bg="black", fg=self.fg_color, font=self.font).pack(side=tk.LEFT)
        
        # Refresh Button (Now shows 00m00s countup in green)
        self.lbl_refresh = tk.Label(self.container, text="[00m00s]", bg="black", fg=self.btn_dim, font=self.btn_font, cursor="hand2")
        self.lbl_refresh.pack(side=tk.LEFT)
        self.lbl_refresh.bind("<Button-1>", self.on_refresh_click)
        
        # Add a small grab handle at the bottom or allow dragging the whole window
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        
        # Context menu for closing
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Close", command=self.destroy)
        self.bind("<Button-3>", self.show_menu)

        self.load_position()
        self.update_ui()

    def load_position(self):
        try:
            with open(get_config_path(), 'r') as f:
                config = json.load(f)
                x = config.get('x', 100)
                y = config.get('y', 100)
                w = config.get('w')
                h = config.get('h')
                if w and h:
                    self.geometry(f"{w}x{h}+{x}+{y}")
                else:
                    self.geometry(f"+{x}+{y}")
        except Exception:
            self.geometry("+100+100")

    def save_position(self):
        try:
            self.update_idletasks()
            config = {
                'x': self.winfo_x(),
                'y': self.winfo_y(),
                'w': self.winfo_width(),
                'h': self.winfo_height(),
            }
            with open(get_config_path(), 'w') as f:
                json.dump(config, f)
        except Exception:
            pass

    def destroy(self):
        self.save_position()
        super().destroy()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
        
    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def on_refresh_click(self, event):
        # Trigger manual or auto refresh
        self.lbl_refresh.config(fg=self.btn_dim) # dim while refreshing
        self.lbl_pct.config(text="--%")
        self.lbl_time.config(text="--:--")
        state["needs_refresh"] = True
        
    def update_ui(self):
        now = time.time()
        
        # Calculate elapsed minutes and seconds mapped to 00m00s display
        elapsed_seconds = int(now - state["last_update_ts"])
        elapsed_minutes = elapsed_seconds // 60
        elapsed_rem_seconds = elapsed_seconds % 60
        
        display_mins = min(elapsed_minutes, 99)
        btn_text = f"[{display_mins:02d}m{elapsed_rem_seconds:02d}s]"
        
        # Check auto-refresh logic
        if now >= state["next_refresh_ts"] and not state["needs_refresh"]:
            state["auto_refresh"] = True
            self.on_refresh_click(None)
        
        # Always update stats from global state
        if not state["needs_refresh"]:
            self.lbl_pct.config(text=f"{state['percentage']}%")
            self.lbl_time.config(text=f"{state['time_left']}")
            self.lbl_refresh.config(text=btn_text, fg=self.btn_active)
        else:
            # While fetching, keep the numeric timer running but keep color dimmed
            self.lbl_refresh.config(text=btn_text, fg=self.btn_dim)
            
        # Re-run after 500ms
        self.after(500, self.update_ui)

# HTTP Request handler for the local server
class LocalRequestHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == '/poll':
            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"needs_refresh": state["needs_refresh"]}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/update':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                state["percentage"] = data.get("percentage", "--")
                
                # Format safety
                time_left = data.get("time_left", "--:--")
                if "h" in time_left: time_left = time_left.replace("h", ":")
                state["time_left"] = time_left
                
                state["needs_refresh"] = False # Reset flag since we got the data
                
                # Reset timers for auto refresh (jitter only on auto-triggered refreshes)
                jitter = random.randint(0, 17) if state["auto_refresh"] else 0
                state["auto_refresh"] = False
                state["last_update_ts"] = time.time()
                state["next_refresh_ts"] = time.time() + (AUTO_REFRESH_MINUTES * 60) + jitter
                
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            except Exception as e:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass

def try_start_server():
    """Bind the port on the main thread first so we can fail fast if it's taken."""
    try:
        httpd = HTTPServer(('127.0.0.1', 8765), LocalRequestHandler)
    except OSError:
        return None
    return httpd

if __name__ == "__main__":
    httpd = try_start_server()
    if httpd is None:
        # Another instance already owns the port. Refuse to start a zombie GUI.
        try:
            import tkinter.messagebox as mb
            root = tk.Tk(); root.withdraw()
            mb.showerror(
                "Claude Widget already running",
                "Another Claude Widget instance is already running on port 8765.\n\n"
                "Close it from the system tray / task manager before launching a new one."
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    app = ClaudeWidget()
    app.mainloop()
