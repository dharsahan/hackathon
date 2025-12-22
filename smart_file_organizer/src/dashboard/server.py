"""
Web Dashboard
=============

Real-time web dashboard for the Smart File Organizer.
Shows live stats, activity feed, and allows undo operations.
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mimetypes

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# HTML template for the dashboard
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart File Organizer - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e4;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(46, 213, 115, 0.2);
            border-radius: 20px;
            font-size: 0.9rem;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #2ed573;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        .card-title {
            font-size: 0.9rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .card-value {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .card-icon {
            font-size: 3rem;
            opacity: 0.3;
            position: absolute;
            right: 20px;
            top: 20px;
        }
        
        .activity-card {
            grid-column: 1 / -1;
        }
        
        .activity-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .activity-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.03);
            margin-bottom: 10px;
            transition: background 0.3s;
        }
        
        .activity-item:hover {
            background: rgba(255, 255, 255, 0.08);
        }
        
        .activity-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        
        .activity-icon.success { background: rgba(46, 213, 115, 0.2); }
        .activity-icon.warning { background: rgba(255, 193, 7, 0.2); }
        .activity-icon.error { background: rgba(255, 71, 87, 0.2); }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-file {
            font-weight: 500;
            color: #fff;
        }
        
        .activity-dest {
            font-size: 0.85rem;
            color: #888;
        }
        
        .activity-time {
            font-size: 0.8rem;
            color: #666;
        }
        
        .undo-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            background: rgba(102, 126, 234, 0.3);
            color: #667eea;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.3s;
        }
        
        .undo-btn:hover {
            background: rgba(102, 126, 234, 0.5);
        }
        
        .undo-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        
        .categories {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        
        .category-tag {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            background: rgba(102, 126, 234, 0.2);
        }
        
        .refresh-info {
            text-align: center;
            color: #666;
            font-size: 0.8rem;
            margin-top: 20px;
        }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🗂️ Smart File Organizer</h1>
            <div class="status">
                <span class="status-dot"></span>
                <span>Running</span>
            </div>
        </header>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">Total Processed</div>
                <div class="card-value" id="total-processed">0</div>
            </div>
            
            <div class="card">
                <div class="card-title">Successful</div>
                <div class="card-value" id="successful">0</div>
            </div>
            
            <div class="card">
                <div class="card-title">Duplicates Found</div>
                <div class="card-value" id="duplicates">0</div>
            </div>
            
            <div class="card">
                <div class="card-title">Sensitive Files</div>
                <div class="card-value" id="sensitive">0</div>
            </div>
            
            <div class="card activity-card">
                <div class="card-title">Recent Activity</div>
                <div class="activity-list" id="activity-list">
                    <div class="activity-item">
                        <div class="activity-icon success">📁</div>
                        <div class="activity-content">
                            <div class="activity-file">Loading...</div>
                            <div class="activity-dest">Please wait</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Categories</div>
                <div class="categories" id="categories">
                    <span class="category-tag">Loading...</span>
                </div>
            </div>
        </div>
        
        <div class="refresh-info">
            Auto-refreshes every 5 seconds • Last updated: <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        function formatTime(isoString) {
            const date = new Date(isoString);
            return date.toLocaleTimeString();
        }
        
        function getFilename(path) {
            return path.split('/').pop();
        }
        
        async function fetchData() {
            try {
                const [statsRes, historyRes] = await Promise.all([
                    fetch('/api/stats'),
                    fetch('/api/history')
                ]);
                
                const stats = await statsRes.json();
                const history = await historyRes.json();
                
                // Update stats
                document.getElementById('total-processed').textContent = stats.total_operations || 0;
                document.getElementById('successful').textContent = stats.undoable || 0;
                document.getElementById('duplicates').textContent = stats.by_category?.Duplicates || 0;
                document.getElementById('sensitive').textContent = stats.by_category?.Sensitive || 0;
                
                // Update categories
                const categoriesDiv = document.getElementById('categories');
                const categories = stats.by_category || {};
                categoriesDiv.innerHTML = Object.entries(categories)
                    .map(([cat, count]) => `<span class="category-tag">${cat}: ${count}</span>`)
                    .join('') || '<span class="category-tag">No data yet</span>';
                
                // Update activity list
                const activityList = document.getElementById('activity-list');
                if (history.length > 0) {
                    activityList.innerHTML = history.map(entry => `
                        <div class="activity-item">
                            <div class="activity-icon success">📁</div>
                            <div class="activity-content">
                                <div class="activity-file">${getFilename(entry.source_path)}</div>
                                <div class="activity-dest">→ ${entry.category}${entry.subcategory ? '/' + entry.subcategory : ''}</div>
                            </div>
                            <div class="activity-time">${formatTime(entry.timestamp)}</div>
                            ${entry.can_undo ? `<button class="undo-btn" onclick="undoEntry(${entry.id})">Undo</button>` : ''}
                        </div>
                    `).join('');
                } else {
                    activityList.innerHTML = `
                        <div class="activity-item">
                            <div class="activity-icon success">📁</div>
                            <div class="activity-content">
                                <div class="activity-file">No activity yet</div>
                                <div class="activity-dest">Drop a file to get started</div>
                            </div>
                        </div>
                    `;
                }
                
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
            } catch (error) {
                console.error('Failed to fetch data:', error);
            }
        }
        
        async function undoEntry(id) {
            try {
                const res = await fetch(`/api/undo/${id}`, { method: 'POST' });
                if (res.ok) {
                    fetchData();
                }
            } catch (error) {
                console.error('Undo failed:', error);
            }
        }
        
        // Initial load
        fetchData();
        
        // Auto-refresh every 5 seconds
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
'''


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard."""
    
    organizer = None  # Set by DashboardServer
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "/dashboard":
            self._serve_dashboard()
        elif path == "/api/stats":
            self._serve_stats()
        elif path == "/api/history":
            self._serve_history()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/api/undo/"):
            entry_id = path.split("/")[-1]
            self._handle_undo(int(entry_id))
        else:
            self._send_404()
    
    def _send_json(self, data: Any, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_html(self, html: str, status: int = 200):
        """Send HTML response."""
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _send_404(self):
        """Send 404 response."""
        self.send_response(404)
        self.end_headers()
    
    def _serve_dashboard(self):
        """Serve the main dashboard HTML."""
        self._send_html(DASHBOARD_HTML)
    
    def _serve_stats(self):
        """Serve statistics API."""
        if self.organizer and hasattr(self.organizer, 'history'):
            stats = self.organizer.history.get_stats()
            self._send_json(stats)
        else:
            self._send_json({})
    
    def _serve_history(self):
        """Serve history API."""
        if self.organizer and hasattr(self.organizer, 'history'):
            entries = self.organizer.history.get_recent(20)
            data = [entry.to_dict() for entry in entries]
            self._send_json(data)
        else:
            self._send_json([])
    
    def _handle_undo(self, entry_id: int):
        """Handle undo request."""
        if self.organizer and hasattr(self.organizer, 'history'):
            result = self.organizer.history.undo_by_id(entry_id)
            if result:
                self._send_json({"success": True})
            else:
                self._send_json({"success": False}, 400)
        else:
            self._send_json({"error": "Organizer not available"}, 500)


class DashboardServer:
    """Web dashboard server for the file organizer."""
    
    def __init__(self, organizer, host: str = "127.0.0.1", port: int = 8080):
        """Initialize the dashboard server.
        
        Args:
            organizer: SmartFileOrganizer instance.
            host: Host to bind to.
            port: Port to listen on.
        """
        self.organizer = organizer
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start the dashboard server."""
        if self._running:
            return
        
        # Set organizer reference in handler
        DashboardHandler.organizer = self.organizer
        
        self._server = HTTPServer((self.host, self.port), DashboardHandler)
        self._running = True
        
        self._thread = threading.Thread(
            target=self._serve,
            daemon=True,
            name="DashboardServer"
        )
        self._thread.start()
        
        logger.info(f"Dashboard started at http://{self.host}:{self.port}")
    
    def _serve(self) -> None:
        """Server loop."""
        while self._running:
            self._server.handle_request()
    
    def stop(self) -> None:
        """Stop the dashboard server."""
        if not self._running:
            return
        
        self._running = False
        if self._server:
            self._server.shutdown()
        
        logger.info("Dashboard stopped")
    
    @property
    def url(self) -> str:
        """Get the dashboard URL."""
        return f"http://{self.host}:{self.port}"
