from itertools import zip_longest
import sys
import os
import httpx
import asyncio
import json
import re
import websockets
import getpass
from pathlib import Path
import time
from nacl.signing import SigningKey
import binascii


VERSION = "1.0.0"
BASE_URL = "https://lumetrix-backend.sidhi.xyz" 
RAW_URL = "https://raw.githubusercontent.com/AnrosPrac/lcli/main"
 # Ensure this is your live URL
# --- REPLACE THE OLD IdleSync CLASS WITH THIS ---
class IdleSync:
    def __init__(self, cli_instance):
        self.cli = cli_instance
        self.threshold = 90  # 3 Minute Idle Threshold
        self.last_push_ts = time.time()
        self.is_running = False


    def is_jlab_environment(self) -> bool:
        """
        Detects if the CLI is running inside a managed JupyterLab/Hub environment.
        Used to restrict cloud auto-sync and manual pushes to college servers.
        """
        markers = [
            "JUPYTERHUB_USER", 
            "JUPYTERHUB_SERVICE_PREFIX", 
            "JPY_PARENT_PID",
            "JUPYTER_RUNTIME_DIR"
        ]
        # Returns True if any marker exists or if 'jupyterhub' is in the current path
        return any(os.environ.get(m) for m in markers) or "jupyterhub" in os.getcwd().lower()
    async def watch_loop(self):
        self.is_running = True
        # Silent mode for background daemon
        ALLOWED = {'.py', '.ipynb', '.c', '.cpp', '.h'}

        while self.is_running:
            await asyncio.sleep(10) 
            await self.cli.check_for_updates()
            latest_edit_time = 0
            has_files = False
            
            for root, _, files in os.walk("."):
                if any(part.startswith('.') for part in Path(root).parts): continue
                for file in files:
                    if Path(file).suffix in ALLOWED:
                        try:
                            mtime = os.path.getmtime(os.path.join(root, file))
                            if mtime > latest_edit_time:
                                latest_edit_time = mtime
                                has_files = True
                        except: continue
            
            if not has_files: continue

            time_since_edit = time.time() - latest_edit_time
            
            # Trigger if we have new work AND the user has been quiet for 3 mins
            if latest_edit_time > self.last_push_ts and time_since_edit >= self.threshold:
                await self.cli.push_to_cloud()
                self.last_push_ts = time.time()
class ClientIdentity:
    def __init__(self):
        self.path = Path.home() / ".lum_client"

    def load_or_create(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            sk = SigningKey(binascii.unhexlify(data["private_key"]))
            return sk

        # First install → generate
        sk = SigningKey.generate()
        vk = sk.verify_key

        data = {
            "private_key": binascii.hexlify(sk.encode()).decode(),
            "public_key": binascii.hexlify(vk.encode()).decode(),
            "created_at": time.time()
        }

        self.path.write_text(json.dumps(data))
        return sk

class StreamHandler:
    def __init__(self, token: str):
        self.token = token
        self.config_file = Path.home() / ".lum_config"

    def _get_authenticated_user(self):
        try:
            if self.config_file.exists():
                data = json.loads(self.config_file.read_text())
                return data.get("sidhi_id")
        except: return None
        return None

    async def start_broadcast(self, filename):
        username = self._get_authenticated_user()
        if not username:
            print("\033[1;31m[!] Identity error. Please run: lum login\033[0m")
            return

        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/source/{username}?token={self.token}"
        
        connect_args = {"ping_interval": 20, "ping_timeout": 20, "close_timeout": 5}

        print(f"[*] Initializing secure stream for {username}...")
        
        try:
            while True:
                try:
                    async with websockets.connect(uri, **connect_args) as ws:
                        last_content = ""
                        while True:
                            if os.path.exists(filename):
                                content = Path(filename).read_text()
                                if content != last_content:
                                    payload = {"code": content, "file": filename, "ts": time.time()}
                                    await ws.send(json.dumps(payload))
                                    last_content = content
                                    
                                    os.system('cls' if os.name == 'nt' else 'clear')
                                    print(f"\033[1;97;41m  LIVE  \033[0m \033[1;30m Streaming as: \033[1;36m{username}\033[0m")
                                    print(f"\033[1;30m" + "━"*50 + "\033[0m")
                                    print(f"\033[1;30m File:     \033[1;33m{filename}\033[0m")
                                    print(f"\033[1;30m Status:   \033[1;32mHealthy & Syncing\033[0m")
                                    print(f"\033[1;30m" + "━"*50 + "\033[0m")
                                    print(f"\n\033[1;30m[Last sync: {time.strftime('%H:%M:%S')}]\033[0m")
                                    print(f"\033[1;30m(Press Ctrl+C to stop stream safely)\033[0m")
                                    
                            await asyncio.sleep(0.5)
                except (websockets.ConnectionClosed, OSError):
                    print(f"\n\033[1;33m[!] Reconnecting to Lum Relay...\033[0m")
                    await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print(f"\n\033[1;36m[*] Stream ended peacefully. Closing connection...\033[0m")
    async def follow_stream(self, target_user):
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/follow/{target_user}"
        
        print(f"[*] Attaching to {target_user}'s session...")

        try:
            async with websockets.connect(uri) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"\033[1;97;45m WATCHING \033[0m \033[1;30m Source: \033[1;36m{target_user}\033[0m")
                    print(f"\033[1;30m" + "━"*70 + "\033[0m")
                    
                    # Code Display Area
                    print(data.get('code', 'Waiting for code...'))
                    
                    # Chat / Info Footer
                    print(f"\n\033[1;30m" + "━"*70 + "\033[0m")
                    print(f"\033[1;37;44m LIVE CHAT \033[0m \033[1;34m (Press Ctrl+C to exit session)\033[0m")
                    
                    # Displaying messages if available in the payload
                    messages = data.get('messages', [])
                    for m in messages[-3:]: # Show last 3 messages
                        print(f" \033[1;32m{m['from']}:\033[0m {m['text']}")
                    
        except KeyboardInterrupt:
            print(f"\n\033[1;35m[*] Detached from stream. Have a great study session!\033[0m")
        except Exception as e:
            print(f"\n\033[1;31m[!] Follower Error: {e}\033[0m")

    async def follow_user(self, target_user):
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/watch/{target_user}?token={self.token}"
        
        try:
            async with websockets.connect(uri, ping_interval=20) as ws:
                while True:
                    raw_data = await ws.recv()
                    data = json.loads(raw_data)

                    if "code" in data:
                        content = data.get("code", "")
                        filename = data.get("file", "Unknown")
                        latency = (time.time() - data.get("ts", time.time())) * 1000
                        
                        lat_color = "\033[1;32m" if latency < 200 else "\033[1;33m"
                        
                        os.system('cls' if os.name == 'nt' else 'clear')
                        
                        # --- Mind-Blowing Header ---
                        print(f"\033[1;97;44m WATCHING \033[0m \033[1;36m @{target_user}\033[0m", end="")
                        print(f"  {lat_color}● {latency:.0f}ms\033[0m")
                        print(f"\033[1;30m" + "━"*60 + "\033[0m")
                        print(f"\033[1;37mFILE: {filename}\033[0m")
                        print(f"\033[1;30m" + "━"*60 + "\033[0m")
                        
                        # --- The Code ---
                        print(f"\033[0m{content}")
                        
                        # --- Footer ---
                        print(f"\n\033[1;30m" + "━"*60 + "\033[0m")
                        print(f"\033[1;30mPress Ctrl+C to stop following\033[0m")

        except Exception as e:
            print(f"\n\033[1;31m[!] Stream Ended or Connection Failed: {e}\033[0m")

        except KeyboardInterrupt:
            print("\n[!] Stopped watching.")
        except Exception as e:
            print(f"\n[!] Stream Disconnected: {e}")



class LumCLI:
    def is_jlab_environment(self) -> bool:
        markers = ["JUPYTERHUB_USER", "JUPYTERHUB_SERVICE_PREFIX", "JPY_PARENT_PID", "JUPYTER_RUNTIME_DIR"]
        return any(os.environ.get(m) for m in markers) or "jupyterhub" in os.getcwd().lower()
    def __init__(self):
        self.config_file = Path.home() / ".lum_config"
        self.token = self._load_local_token()
        self.client = httpx.AsyncClient(timeout=180.0)
        self.time_offset = 0
        self.idle_worker = IdleSync(self)
        
        # --- AUTO-DAEMON TRIGGER ---
        # Don't spawn if we are already the watcher or updating
        if self.is_jlab_environment():
            if len(sys.argv) > 1 and sys.argv[-1] not in ["watch", "login"]:
                self._ensure_daemon()
    async def check_for_updates(self):
        try:
            # Ping the version/health endpoint
            response = await self.client.get(f"{BASE_URL}/version", timeout=5.0)
            if response.status_code == 200:
                remote_version = response.json().get("version")
                
                # Check if current version is less than remote
                if remote_version and remote_version > VERSION:
                    print(f"\n[!] New version detected ({remote_version}). Updating...")
                    
                    # Execute the hello-lumetrix command
                    import subprocess
                    subprocess.Popen(["hello-lumetrix"], shell=True)
        except Exception:
            # Silently fail to not disturb the student's work
            pass
    async def fetch_history(self):
        """Fetch user's AI usage history with beautiful formatting"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/me/history",
                headers=self._signed_headers("/me/history")
            )
            
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("[!] Session expired. Please login again.")
                    return
                
                response = await self.client.get(
                    f"{BASE_URL}/me/history",
                    headers=self._signed_headers("/me/history")
                )
            
            if response.status_code == 200:
                data = response.json()
                logs = data.get("logs", {})
                
                if not logs:
                    print("\n\033[1;33m[i] No activity history found.\033[0m")
                    return
                
                print(f"\n\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
                print(f"\033[1;36m║          📊 AI USAGE HISTORY                            ║\033[0m")
                print(f"\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
                
                # Sort dates in reverse (newest first)
                sorted_dates = sorted(logs.keys(), reverse=True)
                
                total_requests = 0
                command_totals = {}
                
                for date in sorted_dates:
                    day_logs = logs[date]
                    
                    print(f"\033[1;33m📅 {date}\033[0m")
                    print("─" * 60)
                    
                    # Count commands for this day
                    day_commands = {}
                    for log in day_logs:
                        cmd = log.get("command", "unknown")
                        day_commands[cmd] = day_commands.get(cmd, 0) + 1
                        command_totals[cmd] = command_totals.get(cmd, 0) + 1
                        total_requests += 1
                    
                    # Display day summary
                    for cmd, count in sorted(day_commands.items()):
                        emoji = {
                            "ask": "❓",
                            "write": "✍️",
                            "fix": "🔧",
                            "explain": "📖",
                            "trace": "🔍",
                            "diff": "⚖️",
                            "algo": "🧮",
                            "format": "📝"
                        }.get(cmd, "🔹")
                        
                        print(f"  {emoji} {cmd.upper():<12} : {count} request{'s' if count > 1 else ''}")
                    
                    print()
                
                # Overall Summary
                print(f"\033[1;36m{'═' * 60}\033[0m")
                print(f"\033[1;32m📈 TOTAL ACTIVITY SUMMARY\033[0m")
                print("─" * 60)
                
                for cmd, total in sorted(command_totals.items(), key=lambda x: x[1], reverse=True):
                    bar_length = int((total / max(command_totals.values())) * 30)
                    bar = "█" * bar_length
                    print(f"  {cmd.upper():<12} : {bar} {total}")
                
                print("─" * 60)
                print(f"\033[1;97m  TOTAL REQUESTS: {total_requests}\033[0m")
                print(f"\033[1;36m{'═' * 60}\033[0m\n")
            else:
                print(f"\033[1;31m[!] Failed to fetch history: {response.text}\033[0m")
        
        except Exception as e:
            print(f"\033[1;31m[!] Error: {e}\033[0m")


    async def fetch_cloud_history(self):
        """Fetch user's cloud push history with beautiful formatting"""
        try:
            if not self.config_file.exists():
                print("\033[1;31m[!] Not logged in.\033[0m")
                return
            
            data = json.loads(self.config_file.read_text())
            sidhi_id = data.get("sidhi_id")
            
            response = await self.client.get(
                f"{BASE_URL}/me/cloud-history?sidhi_id={sidhi_id}",
                headers=self._signed_headers("/me/cloud-history")
            )
            
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("\033[1;31m[!] Session expired. Please login again.\033[0m")
                    return
                
                response = await self.client.get(
                    f"{BASE_URL}/me/cloud-history?sidhi_id={sidhi_id}",
                    headers=self._signed_headers("/me/cloud-history")
                )
            
            if response.status_code == 200:
                result = response.json()
                pushes = result.get("pushes", [])
                
                if not pushes:
                    print("\n\033[1;33m[i] No cloud sync history found.\033[0m")
                    return
                
                print(f"\n\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
                print(f"\033[1;36m║          ☁️  CLOUD SYNC HISTORY                         ║\033[0m")
                print(f"\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
                
                # Show last 15 pushes (most recent first - already sorted by backend)
                recent_pushes = pushes[-15:][::-1]  # Reverse to show newest first
                
                for idx, push in enumerate(recent_pushes, 1):
                    timestamp = push.get("time", "N/A")
                    icon = "🔵" if idx == 1 else "⚪"
                    
                    print(f"  {icon} \033[1;32m{timestamp}\033[0m")
                
                print(f"\n\033[1;36m{'─' * 60}\033[0m")
                print(f"\033[1;97m  📦 Total Cloud Syncs: {len(pushes)}\033[0m")
                print(f"\033[1;90m  (Showing last {len(recent_pushes)} syncs)\033[0m")
                print(f"\033[1;36m{'─' * 60}\033[0m\n")
            else:
                print(f"\033[1;31m[!] Failed to fetch cloud history: {response.text}\033[0m")
        
        except Exception as e:
            print(f"\033[1;31m[!] Error: {e}\033[0m")


    async def fetch_quotas(self):
        """Fetch user's AI quotas with beautiful formatting"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/me/quotas",
                headers=self._signed_headers("/me/quotas")
            )
            
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("\033[1;31m[!] Session expired. Please login again.\033[0m")
                    return
                
                response = await self.client.get(
                    f"{BASE_URL}/me/quotas",
                    headers=self._signed_headers("/me/quotas")
                )
            
            if response.status_code == 200:
                data = response.json()
                
                tier = data.get("tier", "free").upper()
                base = data.get("base", {})
                used = data.get("used", {})
                addons = data.get("addons", {})
                
                # Tier color
                tier_color = {
                    "FREE": "\033[1;37m",
                    "HERO": "\033[1;33m",
                    "DOMINATOR": "\033[1;35m"
                }.get(tier, "\033[1;37m")
                
                print(f"\n\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
                print(f"\033[1;36m║          {tier_color}⚡ {tier} TIER QUOTAS\033[1;36m                              ║\033[0m")
                print(f"\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
                
                # Commands Section
                print(f"\033[1;33m🛠️  COMMAND QUOTAS\033[0m")
                print("─" * 60)
                
                commands = base.get("commands", {})
                used_commands = used.get("commands", {})
                
                for cmd in sorted(commands.keys()):
                    limit = commands[cmd]
                    used_count = used_commands.get(cmd, 0)
                    addon = addons.get(cmd, 0)
                    
                    total_limit = limit + addon
                    remaining = total_limit - used_count
                    percentage = (used_count / total_limit * 100) if total_limit > 0 else 0
                    
                    # Progress bar
                    bar_length = 20
                    filled = int((used_count / total_limit) * bar_length) if total_limit > 0 else 0
                    bar = "█" * filled + "░" * (bar_length - filled)
                    
                    # Color based on usage
                    if percentage >= 90:
                        color = "\033[1;31m"  # Red
                    elif percentage >= 70:
                        color = "\033[1;33m"  # Yellow
                    else:
                        color = "\033[1;32m"  # Green
                    
                    print(f"  {cmd.upper():<12} {color}[{bar}]\033[0m {used_count}/{total_limit} ({remaining} left)")
                
                print()
                
                # Features Section
                print(f"\033[1;33m🎯 FEATURE QUOTAS\033[0m")
                print("─" * 60)
                
                features = ["inject", "cells", "pdf", "convo"]
                feature_names = {
                    "inject": "Code Injection",
                    "cells": "Notebook Cells",
                    "pdf": "PDF Processing",
                    "convo": "AI Conversations"
                }
                
                for feat in features:
                    limit = base.get(feat, 0)
                    used_count = used.get(feat, 0)
                    addon = addons.get(feat, 0)
                    
                    total_limit = limit + addon
                    remaining = total_limit - used_count
                    percentage = (used_count / total_limit * 100) if total_limit > 0 else 0
                    
                    # Progress bar
                    bar_length = 20
                    filled = int((used_count / total_limit) * bar_length) if total_limit > 0 else 0
                    bar = "█" * filled + "░" * (bar_length - filled)
                    
                    # Color based on usage
                    if percentage >= 90:
                        color = "\033[1;31m"
                    elif percentage >= 70:
                        color = "\033[1;33m"
                    else:
                        color = "\033[1;32m"
                    
                    feature_name = feature_names.get(feat, feat.upper())
                    print(f"  {feature_name:<18} {color}[{bar}]\033[0m {used_count}/{total_limit}")
                
                print(f"\n\033[1;36m{'═' * 60}\033[0m")
                
                # Expiry info if exists
                meta = data.get("meta", {})
                expires_at = meta.get("expires_at")
                if expires_at:
                    from datetime import datetime
                    expiry_date = expires_at.get("$date") if isinstance(expires_at, dict) else expires_at
                    if expiry_date:
                        print(f"\033[1;90m  📅 Expires: {expiry_date[:10]}\033[0m")
                
                print(f"\033[1;36m{'═' * 60}\033[0m\n")
            else:
                print(f"\033[1;31m[!] Failed to fetch quotas: {response.text}\033[0m")
        
        except Exception as e:
            print(f"\033[1;31m[!] Error: {e}\033[0m")


    async def fetch_order_history(self):
        """Fetch user's order history with beautiful formatting"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/orders/history",
                headers=self._signed_headers("/orders/history")
            )
            
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("\033[1;31m[!] Session expired. Please login again.\033[0m")
                    return
                
                response = await self.client.get(
                    f"{BASE_URL}/orders/history",
                    headers=self._signed_headers("/orders/history")
                )
            
            if response.status_code == 200:
                result = response.json()
                orders = result.get("orders", [])
                
                if not orders:
                    print("\n\033[1;33m[i] No orders found.\033[0m")
                    return
                
                print(f"\n\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
                print(f"\033[1;36m║          📦 ORDER HISTORY                                ║\033[0m")
                print(f"\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
                
                for order in orders:
                    order_id = order.get("ORDER_ID", "N/A")
                    folder = order.get("SUMMARY", {}).get("folder_name", "N/A")
                    status = order.get("STATUS", "unknown")
                    placed_at = order.get("PLACED_AT", "N/A")
                    
                    # Status styling
                    if status == "COMPLETED":
                        status_display = "\033[1;32m✓ COMPLETED\033[0m"
                    elif status == "QUEUED":
                        status_display = "\033[1;33m⏳ QUEUED\033[0m"
                    elif status == "PROCESSING":
                        status_display = "\033[1;34m⚙️  PROCESSING\033[0m"
                    else:
                        status_display = f"\033[1;31m✗ {status}\033[0m"
                    
                    print(f"\033[1;97m  Order #{order_id}\033[0m")
                    print(f"  Folder  : \033[1;36m{folder}\033[0m")
                    print(f"  Status  : {status_display}")
                    print(f"  Date    : \033[1;90m{placed_at[:10]}\033[0m")
                    print("─" * 60)
                
                print(f"\n\033[1;97m  📊 Total Orders: {len(orders)}\033[0m")
                print(f"\033[1;36m{'═' * 60}\033[0m\n")
            else:
                print(f"\033[1;31m[!] Failed to fetch orders: {response.text}\033[0m")
        
        except Exception as e:
            print(f"\033[1;31m[!] Error: {e}\033[0m")


    async def fetch_payment_history(self):
        """Fetch user's payment history with beautiful formatting"""
        try:
            response = await self.client.get(
                f"{BASE_URL}/me/payments/history",
                headers=self._signed_headers("/me/payments/history")
            )
            
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("\033[1;31m[!] Session expired. Please login again.\033[0m")
                    return
                
                response = await self.client.get(
                    f"{BASE_URL}/me/payments/history",
                    headers=self._signed_headers("/me/payments/history")
                )
            
            if response.status_code == 200:
                result = response.json()
                payments = result.get("payments", [])
                
                if not payments:
                    print("\n\033[1;33m[i] No payment history found.\033[0m")
                    return
                
                print(f"\n\033[1;36m╔══════════════════════════════════════════════════════════╗\033[0m")
                print(f"\033[1;36m║          💳 PAYMENT HISTORY                              ║\033[0m")
                print(f"\033[1;36m╚══════════════════════════════════════════════════════════╝\033[0m\n")
                
                for payment in payments:
                    tier = payment.get("tier", "N/A").upper()
                    amount = payment.get("amount", 0)
                    status = payment.get("status", "unknown")
                    created = payment.get("created_at", {})
                    expires = payment.get("expires_at", {})
                    
                    # Extract date strings
                    created_date = created.get("$date", "N/A") if isinstance(created, dict) else str(created)
                    expires_date = expires.get("$date", "N/A") if isinstance(expires, dict) else str(expires)
                    
                    # Tier color
                    tier_color = {
                        "HERO": "\033[1;33m",
                        "DOMINATOR": "\033[1;35m",
                        "FREE": "\033[1;37m"
                    }.get(tier, "\033[1;37m")
                    
                    # Status styling
                    if status == "captured":
                        status_display = "\033[1;32m✓ SUCCESSFUL\033[0m"
                    elif status == "failed":
                        status_display = "\033[1;31m✗ FAILED\033[0m"
                    else:
                        status_display = f"\033[1;33m⏳ {status.upper()}\033[0m"
                    
                    print(f"  {tier_color}⚡ {tier} TIER\033[0m")
                    print(f"  Amount  : \033[1;32m₹{amount}\033[0m")
                    print(f"  Status  : {status_display}")
                    print(f"  Paid On : \033[1;90m{created_date[:10]}\033[0m")
                    print(f"  Expires : \033[1;90m{expires_date[:10]}\033[0m")
                    print("─" * 60)
                
                total_spent = sum(p.get("amount", 0) for p in payments if p.get("status") == "captured")
                print(f"\n\033[1;97m  💰 Total Spent: ₹{total_spent}\033[0m")
                print(f"\033[1;36m{'═' * 60}\033[0m\n")
            else:
                print(f"\033[1;31m[!] Failed to fetch payments: {response.text}\033[0m")
        
        except Exception as e:
            print(f"\033[1;31m[!] Error: {e}\033[0m")
    def _ensure_daemon(self):
        """Silently spawns the background watcher if it isn't running."""
        if not self.token: return

        pid_file = Path.home() / ".lum_watcher.pid"
        try:
            if pid_file.exists():
                pid = int(pid_file.read_text())
                os.kill(pid, 0) # Check if process is alive
                return # Already running
        except: pass

        # Spawn detached background process
        import subprocess
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "watch"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )

    def _load_local_token(self):
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text())
                return data.get("access_token")
            except:
                return None
        return None
    async def auto_update(self):
        try:
            print(f"[*] Checking for updates.... (Current: v{VERSION})")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(RAW_URL)
                if resp.status_code == 200:
                    # Look for the VERSION string in the remote code
                    remote_match = re.search(r'VERSION = "([^"]+)"', resp.text)
                    if remote_match:
                        remote_version = remote_match.group(1)
                        
                        if remote_version != VERSION:
                            print(f"[!] New version found: {remote_version}. Installing...")
                            current_file = os.path.abspath(__file__)
                            with open(current_file, "w") as f:
                                f.write(resp.text)
                            print(f"[✔] Update complete. Please restart your command.")
                            sys.exit(0) 
                        else:
                            print(f"\033[90m[v{VERSION}] Engine up to date\033[0m")
        except Exception:
            print("[!] Update check failed (Skipping...)")
    
    
    async def push_to_cloud(self):
        """Detects terminal user and sidhi_id to perform verified sync."""
        print(f"[*] Scanning for code files...")
        files_data = {}
        ALLOWED_EXT = {'.py', '.ipynb', '.c', '.cpp', '.h'}
        total_size_bytes = 0
        MAX_SIZE_BYTES = 2 * 1024 * 1024
        
        # This grabs the "2025123019" from your terminal environment
        college_roll = getpass.getuser() 
        
        sidhi_id = None
        if self.config_file.exists():
            data = json.loads(self.config_file.read_text())
            sidhi_id = data.get("sidhi_id")

        if not sidhi_id:
            print("[!] Please login first: lum login")
            return

        for path in Path('.').rglob('*'):
            if any(part.startswith('.') for part in path.parts): continue
            if path.is_file() and path.suffix.lower() in ALLOWED_EXT:
                try:
                    # Check size before reading
                    file_size = path.stat().st_size
                    if total_size_bytes + file_size > MAX_SIZE_BYTES:
                        print(f"\n[!] ABORT: Total sync size exceeds limit.")
                        return
                    files_data[str(path)] = path.read_text(encoding='utf-8')
                except: continue

        if not files_data: return

        try:
            response = await self.client.post(
                f"{BASE_URL}/sync/push",
                json={
                    "sidhilynx_id": sidhi_id,
                    "college_roll": college_roll,
                    "files": files_data
                },
                headers=self._signed_headers("/sync/push")
            )
            
            if response.status_code == 200:
                print(f"\n\033[1;32m[LUM] Vault user_{sidhi_id} Synchronized.\033[0m")
            else:
                print(f"\033[1;31m[!] Server Rejected: {response.text}\033[0m")
        except Exception as e:
            print(f"[!!!] CONNECTION ERROR: {e}")
    async def sync_clock(self):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{BASE_URL}/health")
                    server_date = resp.headers.get("Date")
                    if server_date:
                        import email.utils
                        server_ts = email.utils.parsedate_to_datetime(server_date).timestamp()
                        self.time_offset = server_ts - time.time()
            except Exception:
                pass

    def get_synced_ts(self):
        return str(int(time.time() + self.time_offset))
    async def generate_notebook(self, input_file, output_file):
        cmd = "format"
        if not Path(input_file).exists():
            print(f"[!] Input file {input_file} not found.")
            return
        content = Path(input_file).read_text()
        
            
            # Note: Changed endpoint to /ai/format specifically for this task
        endpoint = f"{BASE_URL}/ai/format"
                    # REPLACE IN BOTH BLOCKS:
        try:
                # headers = {"Authorization": f"Bearer {self.token}"} <--- REMOVE
                response = await self.client.post(
                    endpoint,
                    json={"text_content": content},
                    headers=self._signed_headers("/ai/format" if cmd == "format" else "/ai/inject") # <--- ADD
                )
                if response.status_code == 200:
                    result = response.json().get("output")
                    if result:
                        Path(input_file).write_text(self.clean_response(result))
                        
                else:
                    print(f"[×] Format failed: {response.text}")
        except Exception as e:
                print(f"[!] CLI Error: {e}") 

           

        content = Path(input_file).read_text()
        print(f"[*] Manufacturing Notebook: {output_file}...")

        try:
            # Send request to our new protected endpoint
            response = await self.client.post(
                f"{BASE_URL}/ai/cells",
                json={"text_content": content},
                headers=self._signed_headers("/ai/cells"),
                timeout=120.0
            )

            if response.status_code == 200:
                data = response.json()
                tasks = data.get("tasks", [])

                # Initialize Jupyter Notebook Structure
                notebook = {
                    "cells": [],
                    "metadata": {
                        "kernelspec": {"display_name": "Python 3", "name": "python3"},
                        "language_info": {"name": "python"}
                    },
                    "nbformat": 4, "nbformat_minor": 4
                }

                for idx, task in enumerate(tasks, 1):
                    def sanitize(text):
                        tags = [
                            r"\[CODE\]", r"\[/CODE\]", 
                            r"\[OUTPUT\]", r"\[/OUTPUT\]",
                            r"\[TERMINAL_START\]"
                        ]
                        for tag in tags:
                            text = re.sub(tag, "", text, flags=re.IGNORECASE)
                        text = re.sub(r"```[a-zA-Z]*\n|```", "", text).strip()
                        return text

                    clean_code = sanitize(task['code'])
                    clean_output = sanitize(task.get('output', ''))

                    # Cell 1: Clean Description (Normal Font)
                    # We use > to keep it in a neat block, but no # headers
                    notebook["cells"].append({
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [f"> {idx}.{task['question']}"]
                    })
                    
                    # Cell 2: Code Cell (With Live Output)
                    notebook["cells"].append({
                        "cell_type": "code",
                        "execution_count": idx,
                        "metadata": {},
                        "outputs": [{
                            "name": "stdout",
                            "output_type": "stream",
                            "text": [clean_output if clean_output else "Execution successful."]
                        }],
                        "source": [line + "\n" for line in clean_code.split("\n")]
                    })

                with open(output_file, "w") as f:
                    json.dump(notebook, f, indent=2)
                
                print(f"[✔] Notebook ready!")
                
                # NEW: Auto-run the code locally to fill the 'outputs' section
                
            else:
                print(f"[!] Server Error: {response.status_code}")
        except Exception as e:
            print(f"[!] Notebook generation failed: {e}")
    def clean_response(self, text):
        """Removes Markdown code blocks (```c, ```json, etc.) from the response."""
        if not isinstance(text, str): return text
        # Remove start/end code fences
        cleaned = re.sub(r"```[a-zA-Z]*\n|```", "", text)
        return cleaned.strip()
    
    async def refresh_token(self) -> bool:
            await self.sync_clock()
            """
            Attempts silent token refresh.
            Returns True if successful, False otherwise.
            """
            if not self.config_file.exists():
                return False

            try:
                data = json.loads(self.config_file.read_text())
                refresh_token = data.get("refresh_token")
                if not refresh_token:
                    return False

                # 🔐 Load client identity
                identity = ClientIdentity()
                signing_key = identity.load_or_create()
                verify_key = signing_key.verify_key

                public_key_hex = binascii.hexlify(verify_key.encode()).decode()
                timestamp = self.get_synced_ts()

                # 🔏 Sign payload: timestamp:refresh_token
                message = f"{timestamp}:{refresh_token}".encode()
                signature = signing_key.sign(message).signature
                signature_hex = binascii.hexlify(signature).decode()

                headers = {
                    "X-Client-Public-Key": public_key_hex,
                    "X-Client-Signature": signature_hex,
                    "X-Client-Timestamp": timestamp
                }

                response = await self.client.post(
                    f"{BASE_URL}/auth/refresh-token",
                    data={"refresh_token": refresh_token},
                    headers=headers
                )

                if response.status_code != 200:
                    return False

                token_data = response.json()
                data["access_token"] = token_data["access_token"]

                self.config_file.write_text(json.dumps(data))
                self.token = token_data["access_token"]
                return True

            except Exception:
                return False

    async def login(self):
        await self.auto_update()
        await self.sync_clock()
        print("--- Lum Engine Secure Login ---")

        sidhi_id = input("Sidhi ID: ")
        password = getpass.getpass("Password: ")

        # 🔐 Load or create client identity
        identity = ClientIdentity()
        signing_key = identity.load_or_create()
        verify_key = signing_key.verify_key

        public_key_hex = binascii.hexlify(verify_key.encode()).decode()
        timestamp = self.get_synced_ts()

        # 🔏 Sign payload: timestamp:sidhi_id
        message = f"{timestamp}:{sidhi_id}".encode()
        signature = signing_key.sign(message).signature
        signature_hex = binascii.hexlify(signature).decode()

        headers = {
            "X-Client-Public-Key": public_key_hex,
            "X-Client-Signature": signature_hex,
            "X-Client-Timestamp": timestamp,

            # 📦 App metadata (STATIC for CLI)
            "X-Platform": "cli",
            "X-App-Id": "lum-cli",
            "X-App-Name": "LumCLI",
            "X-App-Version": "1.0.0"
        }

        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/login",
                json={"sidhi_id": sidhi_id, "password": password},
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                config_data = {
                    "access_token": data["access_token"],
                    "refresh_token": data["refresh_token"],
                    "sidhi_id": data["sidhi_id"]
                }

                self.config_file.write_text(json.dumps(config_data))
                self.token = data["access_token"]

                print(f"[✔] Authenticated as {data['sidhi_id']}")

            else:
                print(f"[×] Login failed: {response.text}")

        except Exception as e:
            print(f"[!] Connection error: {e}")


    async def run_protected_task(self, endpoint, payload):
        if not self.token:
            print("[!] Access Denied: Run 'lum login' first.")
            return None

        try:
            response = await self.client.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
                headers=self._signed_headers(endpoint)
            )

            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("[!] Session expired. Please login again.")
                    return None

                response = await self.client.post(
                    f"{BASE_URL}{endpoint}",
                    json=payload,
                    headers=self._signed_headers(endpoint)
                )

            return response.json()

        except Exception as e:
            print(f"[!] Task Error: {e}")
            return None

    def _signed_headers(self, path: str) -> dict:
        """
        Creates fully signed headers for Sidhi Zero-Trust APIs
        Signature payload: <timestamp>:<request_path>
        """
        if not self.token:
            raise RuntimeError("Not authenticated")

        # Load client identity
        identity = ClientIdentity()
        signing_key = identity.load_or_create()
        verify_key = signing_key.verify_key

        public_key_hex = binascii.hexlify(verify_key.encode()).decode()
        timestamp = self.get_synced_ts() # <--- USE THE SYNCED ONE HERE

    # 🔏 Sign payload
        message = f"{timestamp}:{path}".encode()
        signature = signing_key.sign(message).signature
        signature_hex = binascii.hexlify(signature).decode()

        return {
            "Authorization": f"Bearer {self.token}",
            "X-Client-Public-Key": public_key_hex,
            "X-Client-Signature": signature_hex,
            "X-Client-Timestamp": timestamp,

            # App metadata (STATIC)
            "X-Platform": "cli",
            "X-App-Id": "lum-cli",
            "X-App-Name": "LumCLI",
            "X-App-Version": "1.0.0"
        }

    async def _animate_thinking(self, stop_event):
        label = "LUMETRX"
        dots = ["   ", ".  ", ".. ", "...", " ..", "  .", "   "]
        idx = 0
        while not stop_event.is_set():
            char_idx = idx % len(label)
            word = "".join([label[i].upper() if i == char_idx else label[i].lower() for i in range(len(label))])
            dot_frame = dots[idx % len(dots)]
            sys.stdout.write(f"\r[*] {word} is thinking{dot_frame}")
            sys.stdout.flush()
            await asyncio.sleep(0.15)
            idx += 1
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()

    async def run_ai_task(self, mode, version, input_text):
        await self.sync_clock()
        payload = {
            "mode": mode,
            "version": version,
            "language": "english",
            "input": input_text
        }
        path = "/ai/execute"
        stop_event = asyncio.Event()
        animation_task = asyncio.create_task(self._animate_thinking(stop_event))
        try:
            response = await self.client.post(
                f"{BASE_URL}{path}",
                json=payload,
                headers=self._signed_headers(path)
            )
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    stop_event.set()
                    await animation_task
                    print("[!] Session expired. Please login again.")
                    return None
                response = await self.client.post(
                    f"{BASE_URL}{path}",
                    json=payload,
                    headers=self._signed_headers(path)
                )
            stop_event.set()
            await animation_task
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return response.content
                data = response.json()
                return self.clean_response(data.get("output"))
            print(f"[!] Server Error {response.status_code}: {response.text}")
            return None
        except Exception as e:
            stop_event.set()
            await animation_task
            print(f"[!] Connection failed: {e}")
            return None

    async def check_auth(self):
        if not self.token:
            print("[!] Status: Not Logged In")
            return

        await self.sync_clock()
        
        try:
            identity = ClientIdentity()
            signing_key = identity.load_or_create()
            public_key = binascii.hexlify(signing_key.verify_key.encode()).decode()
            
            print(f"\033[1;36m--- Lum Session Status ---\033[0m")
            print(f"Token:      Active")
            print(f"Identity:   {public_key[:10]}...{public_key[-10:]}")
            print(f"Time Drift: {self.time_offset:.2f} seconds corrected")
            print(f"Endpoint:   {BASE_URL}")
            print(f"\033[1;32m[✔] System ready for Zero-Trust requests\033[0m")
        except Exception as e:
            print(f"[!] Session Corrupted: {e}")
    async def logout(self):
        try:
            if self.config_file.exists():
                self.config_file.unlink()
            
            identity_path = Path.home() / ".lum_client"
            if identity_path.exists():
                identity_path.unlink()
                
            self.token = None
            print("[✔] Logged out successfully. Local session and identity cleared.")
        except Exception as e:
            print(f"[!] Error during logout: {e}")
    
    async def start_chat(self, channel, password):
        # 1. 🔐 Login Guard
        if not self.token:
            print("[!] Not logged in. Run: lum login")
            return

        # 2. 📡 Setup Connection
        username = getpass.getuser()
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        
        # ✅ FIX: Pass token in URL (Bypasses Render header stripping)
        uri = f"{ws_url}/chat/{channel}/{password}/{username}?token={self.token}"

        # 3. 🖥️ Clean UI Start
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\033[1;36m=== 💬 LUM SECURE CHAT: {channel} ===\033[0m")
        print(f"\033[90mConnected as: {username}\033[0m")
        print("─" * 60)

        try:
            # ✅ ROBUST CONNECT: Handles library version differences & Keepalive
            # ping_interval=20 keeps the connection alive on Render/AWS free tiers
            headers = {"Authorization": f"Bearer {self.token}"}
            connect_args = {"ping_interval": 20, "ping_timeout": 20}

            try:
                # Modern websockets
                connection = websockets.connect(uri, extra_headers=headers, **connect_args)
            except TypeError:
                # Older websockets
                connection = websockets.connect(uri, additional_headers=headers, **connect_args)

            async with connection as ws:
                
                # Task A: Receive Messages (Background)
                async def receive():
                    while True:
                        try:
                            raw = await ws.recv()
                            data = json.loads(raw)

                            # Extract data
                            sender = data.get("user", "Unknown")
                            msg = data.get("msg", "")
                            msg_type = data.get("type", "chat")

                            # 🎨 UX Color Coding
                            if sender == username:
                                # Don't print our own echoed message (we print it locally for speed)
                                continue 
                            elif msg_type == "system":
                                prefix = f"\033[1;33m[SYS]\033[0m"
                            else:
                                prefix = f"\033[1;34m[{sender}]\033[0m"

                            # ✨ THE UI TRICK: Clear line -> Print Msg -> Restore Prompt
                            print(f"\r{prefix}: {msg}" + " " * 20) 
                            print(f"\033[1;32m> \033[0m", end="", flush=True)

                        except (websockets.ConnectionClosed, asyncio.CancelledError):
                            break
                        except Exception:
                            continue

                # Task B: Send Messages (User Input)
                async def send():
                    loop = asyncio.get_event_loop()
                    print(f"\033[1;32m> \033[0m", end="", flush=True)
                    
                    while True:
                        try:
                            # 🧵 Run blocking input() in separate thread
                            msg = await loop.run_in_executor(None, input)
                            
                            # Clean up the raw input line
                            print(f"\033[1A\033[K", end="") 

                            if msg.strip().lower() == "/exit":
                                print("\n[👋] Exiting chat...")
                                await ws.close()
                                return

                            if msg.strip():
                                # ✅ PROTOCOL MATCH: Send RAW TEXT
                                # The server's 'receive_text()' expects a string, not JSON.
                                await ws.send(msg)
                                
                                # Print locally for instant feedback (Zero Latency feel)
                                print(f"\r\033[1;32m[You]:\033[0m {msg}")
                                print(f"\033[1;32m> \033[0m", end="", flush=True)

                        except (asyncio.CancelledError, Exception):
                            return

                # Run concurrently
                await asyncio.gather(receive(), send())

        except Exception as e:
            print(f"\n[!] Connection failed: {e}")


    async def handle_command(self, args):
        await self.sync_clock()
        
        if len(args) == 0:
            self.show_help()
            return

        cmd = args[0]

        # 🔐 LOGIN COMMAND (ADD THIS)
        if cmd == "login":
            await self.login()
            return

        
        # 1. FIX: lum fix <filename>
        elif cmd == "fix":
            if len(args) < 2:
                print("[!] Usage: lum fix <filename>")
                return

            filename = args[1]
            path = Path(filename)

            if path.exists():
                content = path.read_text()
                result = await self.run_ai_task("fix", "standard", content)
                
                if result:
                    print(f"\n\033[1;36m[ Lum has prepared a fix for {filename} ]\033[0m")
                    choice = input("Replace current file or create new? (r/n): ").lower().strip()

                    if choice == 'n':
                        new_filename = f"{path.stem}_fixed{path.suffix}"
                        Path(new_filename).write_text(result)
                        print(f"[✔] Fixed version saved as: {new_filename}")
                    else:
                        path.write_text(result)
                        print(f"[✔] {filename} has been updated.")
            else:
                print(f"[!] File {filename} not found.")

        # 2. ALGO: lum algo <filename> (from code) OR lum algo "question" <filename>
        elif cmd == "algo":
            # Scenario A: lum algo file.c (Generate algo from code)
            if os.path.exists(args[1]):
                filename = args[1]
                content = Path(filename).read_text()
                result = await self.run_ai_task("algo", "from_code", content)
                outfile = f"{Path(filename).stem}_algo.txt"
            # Scenario B: lum algo "Sort list" sort.txt (Generate algo from prompt)
            elif len(args) > 2:
                prompt = args[1]
                outfile = args[2]
                result = await self.run_ai_task("algo", "standard", prompt)
            else:
                print("[!] Invalid usage. See help.")
                return

            if result:
                Path(outfile).write_text(result)
                print(f"[✔] Algorithm saved to {outfile}")

        
        elif cmd == "watch":
            # Internal entry point for the background daemon
            pid_file = Path.home() / ".lum_watcher.pid"
            pid_file.write_text(str(os.getpid()))
            await self.idle_worker.watch_loop()
            return
        elif cmd == "commandhistory":
            await self.fetch_history()
            return
        
        elif cmd == "cloudhistory":
            await self.fetch_cloud_history()
            return
        
        elif cmd == "quotas":
            await self.fetch_quotas()
            return
        
        elif cmd == "orderhistory":
            await self.fetch_order_history()
            return
        
        elif cmd == "paymentshistory":
            await self.fetch_payment_history()
            return
        # 3. WRITE: lum write "prompt" <filename>
        elif cmd == "write":
            if len(args) > 2:
                prompt, filename = args[1], args[2]
                result = await self.run_ai_task("write", "standard", prompt)
                if result:
                    Path(filename).write_text(result)
                    print(f"\n\033[1;36m[ Code written to {filename} ]\033[0m")
            else:
                print("[!] Usage: lum write \"prompt\" <filename>")

        
        elif cmd == "ask":
            question = args[1]
            result = await self.run_ai_task("ask", "standard", question)
            if result:
                print(f"\n[Lum]: {result}\n")

        elif cmd == "explain":
            if len(args) > 1:
                filename = args[1]
                if os.path.exists(filename):
                    content = Path(filename).read_text()
                    result = await self.run_ai_task("explain", "from_code", content)
                    if result:
                        print(f"\n\033[95m[LUM EXPLAINER]: {filename}\033[0m")
                        print("=" * 60)
                        print(result)
                        print("=" * 60)
                else:
                    print(f"[!] File {filename} not found.")
            else:
                print("[!] Usage: lum explain <filename>")
        elif cmd == "cells":
            if len(args) < 3:
                print("[!] Usage: lum cells <questions.txt> <output.ipynb>")
            else:
                await self.generate_notebook(args[1], args[2])
        elif cmd == "diff":
            await self.sync_clock()
            if len(args) > 2:
                file1, file2 = args[1], args[2]
                if os.path.exists(file1) and os.path.exists(file2):
                    code1 = Path(file1).read_text()
                    code2 = Path(file2).read_text()
                    
                    payload = {
                        "mode": "diff",
                        "version": "standard",
                        "input1": code1,
                        "input2": code2
                    }
                    
                                        # FIND THIS BLOCK IN YOUR FILE AND REPLACE THE HEADERS LINE:
                    print(f"[*] Comparing logic flow...")
                    try:
                        # headers = {"Authorization": f"Bearer {self.token}"} <--- REMOVE THIS
                        response = await self.client.post(
                            f"{BASE_URL}/ai/execute",
                            json=payload,
                            headers=self._signed_headers("/ai/execute") # <--- ADD THIS
                        )
                        if response.status_code == 200:
                            # Use the same cleanup logic as other commands
                            raw_text = response.json().get("output")
                            result = self.clean_response(raw_text)
                            
                            print(f"\n\033[1;96m[LOGIC DIFF]: {file1} vs {file2}\033[0m")
                            print("━" * 60 + "\n" + result + "\n" + "━" * 60)
                        else:
                            print(f"[!] Server error: {response.status_code}")
                    except Exception as e:
                        print(f"[!] Connection failed: {e}")
                else:
                    print("[!] One or both files not found.")
            else:
                print("[!] Usage: lum diff <file1> <file2>")
        # 7. STREAM: lum stream <file>
        elif cmd == "stream":
            await self.sync_clock()
            if len(args) > 1:
                handler = StreamHandler(self.token)
                await handler.start_broadcast(args[1])

            else:
                print("[!] Usage: lum stream <filename>")

                # Add this inside the handle_command method in LumCLI class
        elif cmd == "logout":
            await self.logout()
            return
        
        
        elif cmd == "status" or cmd == "whoami":
            await self.check_auth()
            return
        
        
        # Bulk Injection: lum inject <filename.txt> <foldername>
        elif cmd == "inject":
            await self.sync_clock()
            if len(args) < 2:
                print("[!] Usage: lum format <filename.txt>")
                return

            filename = args[1]
            if not os.path.exists(filename):
                print(f"[!] File {filename} not found.")
                return

            content = Path(filename).read_text()
           
            
            # Note: Changed endpoint to /ai/format specifically for this task
            endpoint = f"{BASE_URL}/ai/format"
                        # REPLACE IN BOTH BLOCKS:
            try:
                # headers = {"Authorization": f"Bearer {self.token}"} <--- REMOVE
                response = await self.client.post(
                    endpoint,
                    json={"text_content": content},
                    headers=self._signed_headers("/ai/format" if cmd == "format" else "/ai/inject") # <--- ADD
                )

                if response.status_code == 200:
                    result = response.json().get("output")
                    if result:
                        Path(filename).write_text(self.clean_response(result))
                        
                else:
                    print(f"[×] Format failed: {response.text}")
            except Exception as e:
                print(f"[!] CLI Error: {e}")  
            if len(args) < 3:
                print("[!] Usage: lum inject <filename.txt> <foldername>")
                return

            txt_file, folder_name = args[1], args[2]

            if not os.path.exists(txt_file):
                print(f"[!] File {txt_file} not found.")
                return

            print(f"[*] Sending batch request to Lum Engine...")
            with open(txt_file, "r") as f:
                content = f.read()

            try:
               
                response = await self.client.post(
                    f"{BASE_URL}/ai/inject",
                    json={"text_content": content},
                    headers=self._signed_headers("/ai/inject"),
                    timeout=180.0
                )


                if response.status_code == 200:
                    files = response.json().get("files", {})
                    
                    # CLI decides the root: Current Working Directory
                    target_dir = Path(os.getcwd()) / folder_name
                    target_dir.mkdir(parents=True, exist_ok=True)

                    for filename, code in files.items():
                        file_path = target_dir / filename
                        file_path.write_text(code)
                        print(f"  [+] Created: {folder_name}/{filename}")

                    print(f"\n[✔] Injection Complete! '{folder_name}' created in your current directory.")
                else:
                    print(f"[×] Failed: {response.text}")
            except Exception as e:
                print(f"[!] CLI Error: {e}")
        
        
        elif cmd == "format":
            if len(args) < 2:
                print("[!] Usage: lum format <filename.txt>")
                return

            filename = args[1]
            if not os.path.exists(filename):
                print(f"[!] File {filename} not found.")
                return

            content = Path(filename).read_text()
            print(f"[*] Reformatting {filename} via Lum Engine...")
            
            # Note: Changed endpoint to /ai/format specifically for this task
            endpoint = f"{BASE_URL}/ai/format"
                    # REPLACE IN BOTH BLOCKS:
            try:
                # headers = {"Authorization": f"Bearer {self.token}"} <--- REMOVE
                response = await self.client.post(
                    endpoint,
                    json={"text_content": content},
                    headers=self._signed_headers("/ai/format" if cmd == "format" else "/ai/inject") # <--- ADD
                )
                if response.status_code == 200:
                    result = response.json().get("output")
                    if result:
                        Path(filename).write_text(self.clean_response(result))
                        print(f"[✔] {filename} is now formatted for injection.")
                else:
                    print(f"[×] Format failed: {response.text}")
            except Exception as e:
                print(f"[!] CLI Error: {e}")         
        
        
        
        # 8. FOLLOW: lum follow <user>
        elif cmd == "follow":
            if len(args) > 1:
                handler = StreamHandler(self.token)
                await handler.follow_user(args[1])

            else:
                print("[!] Usage: lum follow <username>")
        
        
        # Trace: lum trace <filename>
        elif cmd == "trace":
            if len(args) < 2:
                print("[!] Usage: lum trace <filename>")
                return
            
            filename = args[1]
            if not os.path.exists(filename):
                print(f"[!] File {filename} not found.")
                return

            content = Path(filename).read_text()
            raw_response = await self.run_ai_task("trace", "from_code", content)
            
            if not raw_response:
                print("[!] No data received from server.")
                return

            try:
                data = json.loads(raw_response)
                frames = data.get("frames", []) if isinstance(data, dict) else data
                
                for i, frame in enumerate(frames):
                    print("\033[H\033[J", end="") 
                    
                    progress = (i + 1) / len(frames)
                    bar = "█" * int(20 * progress) + "-" * (20 - int(20 * progress))
                    print(f"\033[1;33mLUM DEBUGGER\033[0m | {filename} | Step {i+1}/{len(frames)} [{bar}]")
                    print("="*70)
                    
                    print(f"\033[1;32mEXEC LINE:\033[0m {frame.get('line_no', '??')}")
                    print(f"\033[1;34mLOGIC:\033[0m {frame.get('explanation', 'Executing...')}")
                    print("-" * 70)
                    
                    print(f"{' [ STACK ] ':-^30}   {' [ HEAP ] ':-^30}")
                    
                    stack_data = frame.get('vars', []) 
                    heap_data = frame.get('heap', [])
                    
                    if isinstance(stack_data, dict):
                        stack_data = [{"name": k, "val": v} for k, v in stack_data.items()]
                    
                    for s, h in zip_longest(stack_data, heap_data):
                        s_line = f"{s['name']}: {s['val']}" if isinstance(s, dict) else str(s or "")
                        h_line = f"{h['addr']} -> {h['val']}" if isinstance(h, dict) else str(h or "")
                        print(f" {s_line:<28} |  {h_line}")
                    
                    print("-" * 70)
                    if 'stdout' in frame:
                        print(f"\033[1;37mSTDOUT:\033[0m {frame.get('stdout', '')}")
                    
                    if i < len(frames) - 1:
                        input("\n\033[5m[ Press Enter for Next Frame ]\033[0m")
                    else:
                        print("\n\033[1;32m[ Execution Finished ]\033[0m")
                        time.sleep(2)
            except Exception as e:
                print(f"[!] Trace Error: UI Rendering failed. \nDetails: {e}")
        
        elif cmd == "sync":
            if not self.is_jlab_environment():
                print("\n\033[1;31m[!] Access Denied: Cloud Sync is restricted to JLab Environments.\033[0m")
                return
            await self.push_to_cloud()
        elif cmd == "chat":
            if len(args) > 2:
                await self.start_chat(args[1], args[2])
            else:
                print("[!] Usage: lum chat <channel_name> <password>")
        

    def show_help(self):
        print(f"""
\033[1;36mLUM CLI - Advanced AI Co-Pilot\033[0m
\033[1;30mVersion: {VERSION} | Zero-Trust Identity Engine\033[0m
{"━"*60}

\033[1;33m[ CORE AI ]\033[0m
  \033[1;32mask\033[0m "question"          : Context-aware coding assistance
  \033[1;32mwrite\033[0m "prompt" <file>  : Generate full source code from a task
  \033[1;32mfix\033[0m <file>               : In-place bug fixing and optimization
  \033[1;32malgo\033[0m <file>              : Extract logical steps or pseudocode
  \033[1;32minject\033[0m <txt> <dir>       : Bulk generate project structure into a folder
  \033[1;32mformat\033[0m <file.txt>        : Prepare text files for project injection

\033[1;33m[ ANALYSIS & DEBUG ]\033[0m
  \033[1;32mtrace\033[0m <file>             : Step-through debugger (Stack/Heap visualization)
  \033[1;32mcells\033[0m <txt> <ipynb>      : Manufacture Jupyter Notebooks from logic
  \033[1;32mdiff\033[0m <f1> <f2>           : Compare logic flow between two files
  \033[1;32mexplain\033[0m <file>          : Deep-dive logic breakdown of source code

\033[1;33m[ LIVE COLLABORATION ]\033[0m
  \033[1;32mstream\033[0m <file>            : Broadcast your live coding session
  \033[1;32mfollow\033[0m <user>            : Watch another student code in real-time
  \033[1;32mchat\033[0m <room> <pass>       : Join a secure, private study channel
\033[1;33m[ SYSTEM ]\033[0m
  \033[1;32mlogin\033[0m                    : Authenticate Zero-Trust identity
  \033[1;32mstatus\033[0m                   : Check session, time-drift, and identity keys
  \033[1;32msync\033[0m                     : Force push local changes to JLab Vault
  \033[1;32mlogout\033[0m                   : Clear local session and security tokens
  
\033[1;33m[ RECORDS & ANALYTICS ]\033[0m
  \033[1;32mcommandhistory\033[0m           : View your AI usage history
  \033[1;32mcloudhistory\033[0m             : View your cloud sync history
  \033[1;32mquotas\033[0m                   : Check your AI request quotas
  \033[1;32morderhistory\033[0m             : View your order history
  \033[1;32mpaymentshistory\033[0m          : View your payment transactions
\033[1;33m[ SYSTEM ]\033[0m
  \033[1;32mlogin\033[0m                    : Authenticate Zero-Trust identity
  \033[1;32mstatus\033[0m                   : Check session, time-drift, and identity keys
  \033[1;32msync\033[0m                    : Force push local changes to JLab Vault
  \033[1;32mlogout\033[0m                   : Clear local session and security tokens
{"━"*60}
\033[1;30mUse 'lum <command>' to execute. Persistence Daemon: Active\033[0m
        """)

async def main():
    lum = LumCLI()
    # Handle "lum <cmd>" vs direct python execution
    if len(sys.argv) > 1:
        start_idx = 2 if sys.argv[1] == "lum" else 1
        await lum.handle_command(sys.argv[start_idx:])
    else:
        lum.show_help()

if __name__ == "__main__":
    try:
        # This wraps the entire engine in a safety net
        asyncio.run(main())
    except KeyboardInterrupt:
        # Catches the global exit signal and shuts down silently
        # without dumping a Python traceback
        sys.exit(0)