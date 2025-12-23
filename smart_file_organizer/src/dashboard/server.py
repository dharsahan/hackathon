"""
Web Dashboard
=============

Real-time web dashboard for the Smart File Organizer.
Shows live stats, activity feed, and allows undo operations.
"""

import json
import threading
from pathlib import Path
from typing import Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# HTML template for the dashboard
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart File Organizer</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0d0d1a 100%);
            color: #e4e4e4;
            min-height: 100vh;
            display: flex;
        }
        
        /* Sidebar */
        .sidebar {
            width: 260px;
            min-height: 100vh;
            background: rgba(15, 15, 35, 0.95);
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            padding: 20px;
            display: flex;
            flex-direction: column;
            position: fixed;
            left: 0;
            top: 0;
            bottom: 0;
            z-index: 100;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px;
            margin-bottom: 30px;
        }
        
        .logo-icon {
            font-size: 2rem;
        }
        
        .logo-text {
            font-size: 1.1rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .nav-section {
            margin-bottom: 25px;
        }
        
        .nav-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #666;
            padding: 0 12px;
            margin-bottom: 10px;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: #888;
            margin-bottom: 4px;
        }
        
        .nav-item:hover {
            background: rgba(102, 126, 234, 0.1);
            color: #fff;
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            color: #fff;
            border: 1px solid rgba(102, 126, 234, 0.3);
        }
        
        .nav-icon { font-size: 1.2rem; }
        .nav-text { font-size: 0.9rem; font-weight: 500; }
        
        .service-status {
            margin-top: auto;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .status-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #22c55e;
            animation: pulse 2s infinite;
        }
        
        .status-dot.stopped { background: #ef4444; animation: none; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            50% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
        }
        
        .service-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .btn-restart {
            background: rgba(102, 126, 234, 0.2);
            color: #667eea;
        }
        
        .btn-restart:hover { background: rgba(102, 126, 234, 0.3); }
        
        /* Main Content */
        .main {
            margin-left: 260px;
            flex: 1;
            padding: 30px;
            min-height: 100vh;
        }
        
        .page { display: none; }
        .page.active { display: block; }
        
        .page-header {
            margin-bottom: 30px;
        }
        
        .page-title {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .page-subtitle {
            color: #666;
            font-size: 0.9rem;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            opacity: 0;
            transition: opacity 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-4px);
            border-color: rgba(102, 126, 234, 0.3);
        }
        
        .stat-card:hover::before { opacity: 1; }
        
        .stat-icon {
            font-size: 2rem;
            margin-bottom: 12px;
            opacity: 0.8;
        }
        
        .stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 4px;
        }
        
        /* Activity Section */
        .section {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 20px;
        }
        
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 1rem;
            font-weight: 600;
        }
        
        .activity-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .activity-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 14px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.02);
            margin-bottom: 8px;
            transition: all 0.2s;
            border: 1px solid transparent;
        }
        
        .activity-item:hover {
            background: rgba(102, 126, 234, 0.05);
            border-color: rgba(102, 126, 234, 0.1);
        }
        
        .activity-icon {
            width: 42px;
            height: 42px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            background: rgba(102, 126, 234, 0.15);
        }
        
        .activity-content { flex: 1; }
        
        .activity-file {
            font-weight: 500;
            color: #fff;
            margin-bottom: 3px;
        }
        
        .activity-dest {
            font-size: 0.8rem;
            color: #666;
        }
        
        .activity-time {
            font-size: 0.75rem;
            color: #555;
        }
        
        .undo-btn {
            padding: 6px 14px;
            border: none;
            border-radius: 6px;
            background: rgba(102, 126, 234, 0.15);
            color: #667eea;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .undo-btn:hover { background: rgba(102, 126, 234, 0.25); }
        
        /* Rules Page */
        .rule-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            margin-bottom: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .rule-toggle {
            width: 44px;
            height: 24px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            position: relative;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .rule-toggle.enabled { background: rgba(102, 126, 234, 0.4); }
        
        .rule-toggle::after {
            content: '';
            position: absolute;
            top: 3px;
            left: 3px;
            width: 18px;
            height: 18px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s;
        }
        
        .rule-toggle.enabled::after { transform: translateX(20px); }
        
        .rule-info { flex: 1; }
        .rule-name { font-weight: 500; margin-bottom: 4px; }
        .rule-pattern { font-size: 0.8rem; color: #666; }
        
        .priority-badge {
            padding: 4px 10px;
            background: rgba(34, 197, 94, 0.15);
            color: #22c55e;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .delete-btn {
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .delete-btn:hover { background: rgba(239, 68, 68, 0.2); }
        
        /* Add Rule Form */
        .add-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .add-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3); }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(5px);
            z-index: 200;
            align-items: center;
            justify-content: center;
        }
        
        .modal.show { display: flex; }
        
        .modal-content {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 30px;
            width: 90%;
            max-width: 450px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .modal-title {
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-label {
            display: block;
            font-size: 0.8rem;
            color: #888;
            margin-bottom: 6px;
        }
        
        .form-input {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            font-size: 0.9rem;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .btn-cancel {
            flex: 1;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: transparent;
            color: #888;
            cursor: pointer;
        }
        
        .btn-save {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 500;
        }
        
        /* Settings Page */
        .settings-group {
            margin-bottom: 25px;
        }
        
        .settings-title {
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
        }
        
        .setting-label { color: #888; font-size: 0.9rem; }
        .setting-value { color: #fff; font-size: 0.9rem; font-weight: 500; }
        
        /* Quarantine Page */
        .quarantine-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 14px;
            background: rgba(239, 68, 68, 0.05);
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid rgba(239, 68, 68, 0.1);
        }
        
        .restore-btn {
            padding: 8px 14px;
            border: none;
            border-radius: 6px;
            background: rgba(34, 197, 94, 0.15);
            color: #22c55e;
            cursor: pointer;
            font-size: 0.8rem;
        }
        
        .restore-btn:hover { background: rgba(34, 197, 94, 0.25); }
        
        /* Settings Page Styles */
        .setting-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .setting-row:last-child { border-bottom: none; }
        
        .setting-info { flex: 1; }
        
        .setting-label {
            display: block;
            font-weight: 500;
            color: #fff;
            margin-bottom: 4px;
        }
        
        .setting-desc {
            font-size: 0.8rem;
            color: #666;
        }
        
        .toggle-switch {
            width: 50px;
            height: 26px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 13px;
            position: relative;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .toggle-switch.enabled { background: rgba(34, 197, 94, 0.4); }
        
        .toggle-switch::after {
            content: '';
            position: absolute;
            top: 3px;
            left: 3px;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s;
        }
        
        .toggle-switch.enabled::after { transform: translateX(24px); }
        
        .setting-select {
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: #fff;
            font-size: 0.9rem;
            cursor: pointer;
        }
        
        .setting-select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .danger-btn {
            padding: 8px 16px;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        
        .danger-btn:hover { background: rgba(239, 68, 68, 0.2); }
        
        .folder-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .folder-item:hover { border-color: rgba(102, 126, 234, 0.2); }
        
        .folder-icon { font-size: 1.3rem; }
        
        .folder-path {
            flex: 1;
            font-size: 0.9rem;
            color: #ccc;
            font-family: monospace;
        }
        
        .remove-folder-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }
        
        .remove-folder-btn:hover { background: rgba(239, 68, 68, 0.2); }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
        
        .empty-state {
            text-align: center;
            padding: 50px 20px;
            color: #666;
        }
        
        .empty-icon { font-size: 3rem; margin-bottom: 15px; opacity: 0.5; }
        
        .categories-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .category-chip {
            padding: 8px 14px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 20px;
            font-size: 0.8rem;
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
    </style>
</head>
<body>
    <!-- Sidebar -->
    <nav class="sidebar">
        <div class="logo">
            <span class="logo-icon">🗂️</span>
            <span class="logo-text">Smart Organizer</span>
        </div>
        
        <div class="nav-section">
            <div class="nav-label">Overview</div>
            <div class="nav-item active" data-page="dashboard">
                <span class="nav-icon">📊</span>
                <span class="nav-text">Dashboard</span>
            </div>
            <div class="nav-item" data-page="history">
                <span class="nav-icon">📜</span>
                <span class="nav-text">History</span>
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-label">Management</div>
            <div class="nav-item" data-page="rules">
                <span class="nav-icon">⚡</span>
                <span class="nav-text">Custom Rules</span>
            </div>
            <div class="nav-item" data-page="quarantine">
                <span class="nav-icon">🔒</span>
                <span class="nav-text">Quarantine</span>
            </div>
            <div class="nav-item" data-page="settings">
                <span class="nav-icon">⚙️</span>
                <span class="nav-text">Settings</span>
            </div>
        </div>
        
        <div class="service-status">
            <div class="status-row">
                <div class="status-indicator">
                    <span class="status-dot" id="status-dot"></span>
                    <span id="status-text">Running</span>
                </div>
                <button class="service-btn btn-restart" onclick="restartService()">Restart</button>
            </div>
        </div>
    </nav>
    
    <!-- Main Content -->
    <main class="main">
        <!-- Dashboard Page -->
        <div class="page active" id="page-dashboard">
            <div class="page-header">
                <h1 class="page-title">Dashboard</h1>
                <p class="page-subtitle">Real-time overview of file organization</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📁</div>
                    <div class="stat-value" id="stat-total">0</div>
                    <div class="stat-label">Total Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">✅</div>
                    <div class="stat-value" id="stat-success">0</div>
                    <div class="stat-label">Successful</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📋</div>
                    <div class="stat-value" id="stat-duplicates">0</div>
                    <div class="stat-label">Duplicates</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">💾</div>
                    <div class="stat-value" id="stat-size">0 MB</div>
                    <div class="stat-label">Total Size</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">Recent Activity</h3>
                </div>
                <div class="activity-list" id="activity-list">
                    <div class="empty-state">
                        <div class="empty-icon">📂</div>
                        <div>No activity yet. Drop a file to get started!</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">Categories</h3>
                </div>
                <div class="categories-grid" id="categories-grid">
                    <span class="category-chip">Loading...</span>
                </div>
            </div>
        </div>
        
        <!-- History Page -->
        <div class="page" id="page-history">
            <div class="page-header">
                <h1 class="page-title">History</h1>
                <p class="page-subtitle">Complete history of organized files</p>
            </div>
            <div class="section">
                <div class="activity-list" id="full-history" style="max-height: 600px;"></div>
            </div>
        </div>
        
        <!-- Rules Page -->
        <div class="page" id="page-rules">
            <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h1 class="page-title">Custom Rules</h1>
                    <p class="page-subtitle">Define patterns to auto-categorize files</p>
                </div>
                <button class="add-btn" onclick="showAddRuleModal()">+ Add Rule</button>
            </div>
            <div class="section">
                <div id="rules-list"></div>
            </div>
        </div>
        
        <!-- Quarantine Page -->
        <div class="page" id="page-quarantine">
            <div class="page-header">
                <h1 class="page-title">Quarantine</h1>
                <p class="page-subtitle">Duplicates and sensitive files</p>
            </div>
            <div class="section">
                <div id="quarantine-list"></div>
            </div>
        </div>
        
        <!-- Settings Page -->
        <div class="page" id="page-settings">
            <div class="page-header">
                <h1 class="page-title">Settings</h1>
                <p class="page-subtitle">Configure file organization behavior</p>
            </div>
            
            <!-- Watch Directories Section -->
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">📁 Watch Directories</h3>
                    <button class="add-btn" onclick="showAddFolderModal()" style="padding: 8px 16px; font-size: 0.85rem;">+ Add Folder</button>
                </div>
                <p style="color: #666; font-size: 0.85rem; margin-bottom: 15px;">Folders being monitored for new files</p>
                <div id="watch-dirs-list"></div>
            </div>
            
            <!-- Organization Settings -->
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">🗂️ Organization</h3>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Base Directory</span>
                        <span class="setting-desc">Where organized files are stored</span>
                    </div>
                    <span class="setting-value" id="base-dir">~/Organized</span>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Organize In-Place</span>
                        <span class="setting-desc">Keep files in watched directories</span>
                    </div>
                    <div class="toggle-switch" id="toggle-inplace" onclick="toggleSetting('organize_in_place')"></div>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Use Date Folders</span>
                        <span class="setting-desc">Organize by year/month subfolders</span>
                    </div>
                    <div class="toggle-switch enabled" id="toggle-datefolders" onclick="toggleSetting('use_date_folders')"></div>
                </div>
            </div>
            
            <!-- Classification Settings -->
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">🤖 Classification</h3>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">LLM Model</span>
                        <span class="setting-desc">Model used for AI classification</span>
                    </div>
                    <span class="setting-value" id="llm-model">gemma3:270m</span>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">OCR Enabled</span>
                        <span class="setting-desc">Extract text from images</span>
                    </div>
                    <div class="toggle-switch enabled" id="toggle-ocr" onclick="toggleSetting('ocr_enabled')"></div>
                </div>
            </div>
            
            <!-- Deduplication Settings -->
            <div class="section">
                <div class="section-header">
                    <h3 class="section-title">🔍 Deduplication</h3>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Enable Deduplication</span>
                        <span class="setting-desc">Detect and handle duplicate files</span>
                    </div>
                    <div class="toggle-switch enabled" id="toggle-dedup" onclick="toggleSetting('dedup_enabled')"></div>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Duplicate Action</span>
                        <span class="setting-desc">What to do with duplicates</span>
                    </div>
                    <select class="setting-select" id="dedup-action" onchange="updateDedupAction()">
                        <option value="quarantine">Quarantine</option>
                        <option value="skip">Skip</option>
                        <option value="delete">Delete</option>
                    </select>
                </div>
            </div>
            
            <!-- Actions -->
            <div class="section" style="background: rgba(239, 68, 68, 0.05); border-color: rgba(239, 68, 68, 0.1);">
                <div class="section-header">
                    <h3 class="section-title" style="color: #ef4444;">⚠️ Danger Zone</h3>
                </div>
                <div class="setting-row">
                    <div class="setting-info">
                        <span class="setting-label">Clear History</span>
                        <span class="setting-desc">Delete all operation history</span>
                    </div>
                    <button class="danger-btn" onclick="clearHistory()">Clear</button>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Add Folder Modal -->
    <div class="modal" id="add-folder-modal">
        <div class="modal-content">
            <h3 class="modal-title">Add Watch Folder</h3>
            <div class="form-group">
                <label class="form-label">Folder Path</label>
                <input type="text" class="form-input" id="folder-path" placeholder="/home/user/Documents">
            </div>
            <p style="color: #666; font-size: 0.8rem; margin-bottom: 15px;">
                💡 Common paths: ~/Downloads, ~/Desktop, ~/Documents
            </p>
            <div class="modal-actions">
                <button class="btn-cancel" onclick="hideFolderModal()">Cancel</button>
                <button class="btn-save" onclick="addWatchFolder()">Add Folder</button>
            </div>
        </div>
    </div>
    
    <!-- Add Rule Modal -->
    <div class="modal" id="add-rule-modal">
        <div class="modal-content">
            <h3 class="modal-title">Add Custom Rule</h3>
            <div class="form-group">
                <label class="form-label">Rule Name</label>
                <input type="text" class="form-input" id="rule-name" placeholder="e.g., Work Invoices">
            </div>
            <div class="form-group">
                <label class="form-label">Pattern</label>
                <input type="text" class="form-input" id="rule-pattern" placeholder="e.g., invoice, receipt">
            </div>
            <div class="form-group">
                <label class="form-label">Category</label>
                <input type="text" class="form-input" id="rule-category" placeholder="e.g., Documents">
            </div>
            <div class="form-group">
                <label class="form-label">Subcategory</label>
                <input type="text" class="form-input" id="rule-subcategory" placeholder="e.g., Invoices">
            </div>
            <div class="form-group">
                <label class="form-label">Priority (1-100)</label>
                <input type="number" class="form-input" id="rule-priority" value="50" min="1" max="100">
            </div>
            <div class="modal-actions">
                <button class="btn-cancel" onclick="hideModal()">Cancel</button>
                <button class="btn-save" onclick="saveRule()">Save Rule</button>
            </div>
        </div>
    </div>
    
    <script>
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                document.getElementById('page-' + item.dataset.page).classList.add('active');
                
                if (item.dataset.page === 'rules') loadRules();
                if (item.dataset.page === 'quarantine') loadQuarantine();
                if (item.dataset.page === 'history') loadFullHistory();
                if (item.dataset.page === 'settings') loadSettings();
            });
        });
        
        // Utility functions
        function formatTime(iso) {
            return new Date(iso).toLocaleTimeString();
        }
        
        function getFilename(path) {
            return path.split('/').pop();
        }
        
        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
            if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
            return (bytes / 1073741824).toFixed(1) + ' GB';
        }
        
        // Fetch and update dashboard
        async function fetchData() {
            try {
                const [statsRes, historyRes] = await Promise.all([
                    fetch('/api/stats'),
                    fetch('/api/history')
                ]);
                
                const stats = await statsRes.json();
                const history = await historyRes.json();
                
                // Update stats
                document.getElementById('stat-total').textContent = stats.total_operations || 0;
                document.getElementById('stat-success').textContent = stats.undoable || 0;
                document.getElementById('stat-duplicates').textContent = stats.by_category?.Duplicates || 0;
                document.getElementById('stat-size').textContent = formatSize(stats.total_size_bytes || 0);
                
                // Update categories
                const categories = stats.by_category || {};
                document.getElementById('categories-grid').innerHTML = Object.entries(categories)
                    .map(([cat, count]) => `<span class="category-chip">${cat}: ${count}</span>`)
                    .join('') || '<span class="category-chip">No data</span>';
                
                // Update activity
                const activityList = document.getElementById('activity-list');
                if (history.length > 0) {
                    activityList.innerHTML = history.slice(0, 10).map(entry => `
                        <div class="activity-item">
                            <div class="activity-icon">📁</div>
                            <div class="activity-content">
                                <div class="activity-file">${getFilename(entry.source_path)}</div>
                                <div class="activity-dest">→ ${entry.category}${entry.subcategory ? '/' + entry.subcategory : ''}</div>
                            </div>
                            <div class="activity-time">${formatTime(entry.timestamp)}</div>
                            ${entry.can_undo ? `<button class="undo-btn" onclick="undoEntry(${entry.id})">Undo</button>` : ''}
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }
        
        async function loadFullHistory() {
            try {
                const res = await fetch('/api/history?limit=50');
                const history = await res.json();
                
                document.getElementById('full-history').innerHTML = history.map(entry => `
                    <div class="activity-item">
                        <div class="activity-icon">📁</div>
                        <div class="activity-content">
                            <div class="activity-file">${getFilename(entry.source_path)}</div>
                            <div class="activity-dest">→ ${entry.category}${entry.subcategory ? '/' + entry.subcategory : ''}</div>
                        </div>
                        <div class="activity-time">${formatTime(entry.timestamp)}</div>
                        ${entry.can_undo ? `<button class="undo-btn" onclick="undoEntry(${entry.id})">Undo</button>` : ''}
                    </div>
                `).join('') || '<div class="empty-state"><div class="empty-icon">📂</div><div>No history</div></div>';
            } catch (e) {}
        }
        
        async function loadRules() {
            try {
                const res = await fetch('/api/rules');
                const rules = await res.json();
                
                document.getElementById('rules-list').innerHTML = rules.map(rule => `
                    <div class="rule-item">
                        <div class="rule-toggle ${rule.enabled ? 'enabled' : ''}" onclick="toggleRule(${rule.id}, ${!rule.enabled})"></div>
                        <div class="rule-info">
                            <div class="rule-name">${rule.name}</div>
                            <div class="rule-pattern">Pattern: "${rule.pattern}" → ${rule.category}/${rule.subcategory || ''}</div>
                        </div>
                        <span class="priority-badge">P${rule.priority}</span>
                        <button class="delete-btn" onclick="deleteRule(${rule.id})">🗑️</button>
                    </div>
                `).join('') || '<div class="empty-state"><div class="empty-icon">⚡</div><div>No custom rules</div></div>';
            } catch (e) {}
        }
        
        async function loadQuarantine() {
            try {
                const res = await fetch('/api/quarantine');
                const files = await res.json();
                
                document.getElementById('quarantine-list').innerHTML = files.map(file => `
                    <div class="quarantine-item">
                        <div class="activity-icon" style="background: rgba(239, 68, 68, 0.15);">🔒</div>
                        <div class="activity-content">
                            <div class="activity-file">${file.name}</div>
                            <div class="activity-dest">${file.reason} • ${formatSize(file.size)}</div>
                        </div>
                        <button class="restore-btn" onclick="restoreFile('${file.path}')">Restore</button>
                    </div>
                `).join('') || '<div class="empty-state"><div class="empty-icon">✨</div><div>Quarantine is empty</div></div>';
            } catch (e) {}
        }
        
        async function undoEntry(id) {
            await fetch(`/api/undo/${id}`, { method: 'POST' });
            fetchData();
        }
        
        async function toggleRule(id, enabled) {
            await fetch(`/api/rules/${id}/toggle`, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            loadRules();
        }
        
        async function deleteRule(id) {
            await fetch(`/api/rules/${id}`, { method: 'DELETE' });
            loadRules();
        }
        
        async function restoreFile(path) {
            await fetch('/api/restore', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            loadQuarantine();
        }
        
        function showAddRuleModal() {
            document.getElementById('add-rule-modal').classList.add('show');
        }
        
        function hideModal() {
            document.getElementById('add-rule-modal').classList.remove('show');
        }
        
        async function saveRule() {
            const rule = {
                name: document.getElementById('rule-name').value,
                pattern: document.getElementById('rule-pattern').value,
                category: document.getElementById('rule-category').value,
                subcategory: document.getElementById('rule-subcategory').value,
                priority: parseInt(document.getElementById('rule-priority').value)
            };
            
            await fetch('/api/rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rule)
            });
            
            hideModal();
            loadRules();
        }
        
        function restartService() {
            fetch('/api/restart', { method: 'POST' });
        }
        
        // Settings functions
        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const settings = await res.json();
                
                // Update watch directories
                const dirsEl = document.getElementById('watch-dirs-list');
                if (settings.watch_directories && settings.watch_directories.length > 0) {
                    dirsEl.innerHTML = settings.watch_directories.map(dir => `
                        <div class="folder-item">
                            <span class="folder-icon">📂</span>
                            <span class="folder-path">${dir}</span>
                            <button class="remove-folder-btn" onclick="removeWatchFolder('${dir}')">Remove</button>
                        </div>
                    `).join('');
                } else {
                    dirsEl.innerHTML = '<div class="empty-state"><div class="empty-icon">📁</div><div>No watch folders</div></div>';
                }
                
                // Update settings values
                document.getElementById('base-dir').textContent = settings.base_directory || '~/Organized';
                document.getElementById('llm-model').textContent = settings.llm_model || 'gemma3:270m';
                
                // Update toggles
                if (settings.organize_in_place) {
                    document.getElementById('toggle-inplace').classList.add('enabled');
                } else {
                    document.getElementById('toggle-inplace').classList.remove('enabled');
                }
                
                if (settings.use_date_folders) {
                    document.getElementById('toggle-datefolders').classList.add('enabled');
                } else {
                    document.getElementById('toggle-datefolders').classList.remove('enabled');
                }
                
                if (settings.ocr_enabled) {
                    document.getElementById('toggle-ocr').classList.add('enabled');
                } else {
                    document.getElementById('toggle-ocr').classList.remove('enabled');
                }
                
                if (settings.dedup_enabled) {
                    document.getElementById('toggle-dedup').classList.add('enabled');
                } else {
                    document.getElementById('toggle-dedup').classList.remove('enabled');
                }
                
                // Set duplicate action dropdown
                if (settings.duplicate_action) {
                    document.getElementById('dedup-action').value = settings.duplicate_action;
                }
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        }
        
        function showAddFolderModal() {
            document.getElementById('add-folder-modal').classList.add('show');
        }
        
        function hideFolderModal() {
            document.getElementById('add-folder-modal').classList.remove('show');
        }
        
        async function addWatchFolder() {
            const path = document.getElementById('folder-path').value.trim();
            if (!path) return;
            
            // Expand ~ to home directory
            const expandedPath = path.replace(/^~/, '/home/' + (await getHomeDir()));
            
            await fetch('/api/settings/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            
            hideFolderModal();
            document.getElementById('folder-path').value = '';
            loadSettings();
        }
        
        async function getHomeDir() {
            try {
                const res = await fetch('/api/settings');
                const settings = await res.json();
                if (settings.watch_directories && settings.watch_directories.length > 0) {
                    const match = settings.watch_directories[0].match(/^\/home\/([^/]+)/);
                    return match ? match[1] : 'user';
                }
            } catch (e) {}
            return 'user';
        }
        
        async function removeWatchFolder(path) {
            if (!confirm('Remove this folder from monitoring?')) return;
            
            await fetch('/api/settings/folders', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            
            loadSettings();
        }
        
        async function toggleSetting(setting) {
            const el = document.getElementById('toggle-' + setting.replace(/_/g, '').replace('organize', 'inplace').replace('use', '').replace('ocr', 'ocr').replace('dedup', 'dedup'));
            const currentlyEnabled = el && el.classList.contains('enabled');
            
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [setting]: !currentlyEnabled })
            });
            
            loadSettings();
        }
        
        async function updateDedupAction() {
            const action = document.getElementById('dedup-action').value;
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ duplicate_action: action })
            });
        }
        
        async function clearHistory() {
            if (!confirm('Are you sure you want to clear all history? This cannot be undone.')) return;
            
            await fetch('/api/history/clear', { method: 'POST' });
            fetchData();
        }
        
        // Initial load
        fetchData();
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
        query = parse_qs(parsed.query)

        if path == "/" or path == "/dashboard":
            self._serve_dashboard()
        elif path == "/api/stats":
            self._serve_stats()
        elif path == "/api/history":
            limit = int(query.get('limit', [20])[0])
            self._serve_history(limit)
        elif path == "/api/rules":
            self._serve_rules()
        elif path == "/api/quarantine":
            self._serve_quarantine()
        elif path == "/api/settings":
            self._serve_settings()
        else:
            self._send_404()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Read body if present
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if path.startswith("/api/undo/"):
            entry_id = path.split("/")[-1]
            self._handle_undo(int(entry_id))
        elif path == "/api/rules":
            self._add_rule(data)
        elif path.startswith("/api/rules/") and path.endswith("/toggle"):
            rule_id = int(path.split("/")[-2])
            self._toggle_rule(rule_id, data.get('enabled', True))
        elif path == "/api/restore":
            self._restore_file(data.get('path', ''))
        elif path == "/api/restart":
            self._restart_service()
        elif path == "/api/settings":
            self._update_settings(data)
        elif path == "/api/settings/folders":
            self._add_watch_folder(data.get('path', ''))
        elif path == "/api/history/clear":
            self._clear_history()
        else:
            self._send_404()

    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path.startswith("/api/rules/"):
            rule_id = int(path.split("/")[-1])
            self._delete_rule(rule_id)
        elif path == "/api/settings/folders":
            self._remove_watch_folder(data.get('path', ''))
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

    def _serve_history(self, limit: int = 20):
        """Serve history API."""
        if self.organizer and hasattr(self.organizer, 'history'):
            entries = self.organizer.history.get_recent(limit)
            data = [entry.to_dict() for entry in entries]
            self._send_json(data)
        else:
            self._send_json([])

    def _serve_rules(self):
        """Serve rules API."""
        if self.organizer and hasattr(self.organizer, 'rules_engine'):
            rules = self.organizer.rules_engine.get_rules()
            data = [rule.to_dict() for rule in rules]
            self._send_json(data)
        else:
            self._send_json([])

    def _serve_quarantine(self):
        """Serve quarantine files API."""
        try:
            if self.organizer and hasattr(self.organizer, 'config'):
                quarantine_dir = Path(self.organizer.config.organization.base_directory) / ".quarantine"
                files = []

                if quarantine_dir.exists():
                    # Scan duplicate and sensitive subdirs
                    for subdir in ['duplicate', 'sensitive']:
                        sub_path = quarantine_dir / subdir
                        if sub_path.exists():
                            for f in sub_path.iterdir():
                                if f.is_file():
                                    files.append({
                                        'name': f.name,
                                        'path': str(f),
                                        'size': f.stat().st_size,
                                        'reason': 'Duplicate' if subdir == 'duplicate' else 'Sensitive'
                                    })

                self._send_json(files)
            else:
                self._send_json([])
        except Exception:
            self._send_json([])

    def _add_rule(self, data: dict):
        """Add a new rule."""
        if self.organizer and hasattr(self.organizer, 'rules_engine'):
            self.organizer.rules_engine.add_rule(
                name=data.get('name', 'Custom Rule'),
                pattern=data.get('pattern', ''),
                category=data.get('category', 'Documents'),
                subcategory=data.get('subcategory', ''),
                priority=data.get('priority', 50)
            )
            self._send_json({"success": True})
        else:
            self._send_json({"error": "Rules engine not available"}, 500)

    def _toggle_rule(self, rule_id: int, enabled: bool):
        """Toggle a rule."""
        if self.organizer and hasattr(self.organizer, 'rules_engine'):
            self.organizer.rules_engine.enable_rule(rule_id, enabled)
            self._send_json({"success": True})
        else:
            self._send_json({"error": "Rules engine not available"}, 500)

    def _delete_rule(self, rule_id: int):
        """Delete a rule."""
        if self.organizer and hasattr(self.organizer, 'rules_engine'):
            self.organizer.rules_engine.remove_rule(rule_id)
            self._send_json({"success": True})
        else:
            self._send_json({"error": "Rules engine not available"}, 500)

    def _restore_file(self, path: str):
        """Restore a file from quarantine."""
        try:
            src = Path(path)
            if src.exists() and '.quarantine' in str(src):
                # Move back to Downloads
                dest = Path.home() / "Downloads" / src.name
                src.rename(dest)
                self._send_json({"success": True, "restored_to": str(dest)})
            else:
                self._send_json({"error": "File not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _restart_service(self):
        """Restart the systemd service."""
        import subprocess
        try:
            subprocess.Popen(['systemctl', '--user', 'restart', 'smart-file-organizer'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._send_json({"success": True})
        except:
            self._send_json({"error": "Failed to restart"}, 500)

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
    
    def _serve_settings(self):
        """Serve current settings."""
        try:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            watcher = config.get('watcher', {})
            org = config.get('organization', {})
            classification = config.get('classification', {})
            dedup = config.get('deduplication', {})
            
            settings = {
                'watch_directories': watcher.get('directories', []),
                'base_directory': org.get('base_directory', str(Path.home() / 'Organized')),
                'organize_in_place': org.get('organize_in_place', False),
                'use_date_folders': org.get('use_date_folders', True),
                'llm_model': classification.get('llm_model', 'gemma3:270m'),
                'ocr_enabled': classification.get('ocr_enabled', True),
                'dedup_enabled': dedup.get('enabled', True),
                'duplicate_action': dedup.get('duplicate_action', 'quarantine'),
            }
            
            self._send_json(settings)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _update_settings(self, data: dict):
        """Update settings in config.yaml."""
        try:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            # Apply updates
            if 'organize_in_place' in data:
                config.setdefault('organization', {})['organize_in_place'] = data['organize_in_place']
            if 'use_date_folders' in data:
                config.setdefault('organization', {})['use_date_folders'] = data['use_date_folders']
            if 'ocr_enabled' in data:
                config.setdefault('classification', {})['ocr_enabled'] = data['ocr_enabled']
            if 'dedup_enabled' in data:
                config.setdefault('deduplication', {})['enabled'] = data['dedup_enabled']
            if 'duplicate_action' in data:
                config.setdefault('deduplication', {})['duplicate_action'] = data['duplicate_action']
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _add_watch_folder(self, path: str):
        """Add a new watch folder."""
        try:
            if not path:
                self._send_json({"error": "Path is required"}, 400)
                return
            
            # Expand ~ to home directory
            if path.startswith('~'):
                path = str(Path.home() / path[2:])
            
            # Validate path exists
            folder = Path(path)
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
            
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            dirs = config.setdefault('watcher', {}).setdefault('directories', [])
            if path not in dirs:
                dirs.append(path)
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self._send_json({"success": True, "path": path})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _remove_watch_folder(self, path: str):
        """Remove a watch folder."""
        try:
            if not path:
                self._send_json({"error": "Path is required"}, 400)
                return
            
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            dirs = config.get('watcher', {}).get('directories', [])
            if path in dirs:
                dirs.remove(path)
                config['watcher']['directories'] = dirs
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _clear_history(self):
        """Clear all history."""
        try:
            if self.organizer and hasattr(self.organizer, 'history'):
                self.organizer.history.clear_history()
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


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
