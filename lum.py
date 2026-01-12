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


VERSION = "1.1.0"
BASE_URL = "https://test-termial.onrender.com" 
RAW_URL = "https://raw.githubusercontent.com/AnrosPrac/lcli/main"
 # Ensure this is your live URL
class IdleSync:
    def __init__(self, cli_instance):
        self.cli = cli_instance
        self.last_activity = time.time()
        self.threshold = 600 # 10 Minutes Inactivity
        self.pending_sync = False
        self.is_running = False

    def notify_activity(self):
        self.last_activity = time.time()
        self.pending_sync = True

    async def watch_loop(self):
        self.is_running = True
        while self.is_running:
            await asyncio.sleep(60) # Check status every minute
            idle_time = time.time() - self.last_activity
            
            if self.pending_sync and idle_time >= self.threshold:
                # Trigger the thin push
                await self.cli.push_to_cloud()
                self.pending_sync = False
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
        except:
            return None
        return None

    async def start_broadcast(self, filename):
        username = self._get_authenticated_user()
        if not username:
            print("\033[1;31m[!] Identity error. Please run: lum login\033[0m")
            return

        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/source/{username}?token={self.token}"
        
        connect_args = {
            "ping_interval": 20, 
            "ping_timeout": 20,
            "close_timeout": 5
        }

        while True:
            try:
                async with websockets.connect(uri, **connect_args) as ws:
                    last_content = ""
                    while True:
                        if os.path.exists(filename):
                            content = Path(filename).read_text()
                            if content != last_content:
                                payload = {
                                    "code": content,
                                    "file": filename,
                                    "ts": time.time()
                                }
                                await ws.send(json.dumps(payload))
                                last_content = content
                                
                                os.system('cls' if os.name == 'nt' else 'clear')
                                print(f"\033[1;97;41m  LIVE  \033[0m \033[1;30m Streaming as: \033[1;36m{username}\033[0m")
                                print(f"\033[1;30m" + "━"*50 + "\033[0m")
                                print(f"\033[1;30m File:     \033[1;33m{filename}\033[0m")
                                print(f"\033[1;30m Status:   \033[1;32mHealthy & Syncing\033[0m")
                                print(f"\033[1;30m" + "━"*50 + "\033[0m")
                                print(f"\n\033[1;30m[Last sync: {time.strftime('%H:%M:%S')}]\033[0m")
                                
                        await asyncio.sleep(0.1)

            except Exception as e:
                print(f"\n\033[1;31m[!] Connection Lost: {e}\033[0m")
                await asyncio.sleep(3)
                continue

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

        except KeyboardInterrupt:
            print("\n[!] Stopped watching.")
        except Exception as e:
            print(f"\n[!] Stream Disconnected: {e}")


class LumCLI:
    def __init__(self):
        self.config_file = Path.home() / ".lum_config"
        self.token = self._load_local_token()
        self.client = httpx.AsyncClient(timeout=180.0)
        self.time_offset = 0
        self.idle_worker = IdleSync(self)
        # Create a non-blocking background task
        asyncio.create_task(self.idle_worker.watch_loop())

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
        """Filters files and triggers the Render Server sync."""
        files_data = {}
        blacklist = {'.local', '.cache', '.npm', '.jupyter', '.ipython', '.config', '.git', '.mozilla', '.ssh', '__pycache__'}
        
        current_size = 0
        for path in Path('.').rglob('*'):
            if any(part in blacklist for part in path.parts): continue
            
            # Added .c, .cpp, .h for C programming support
            if path.is_file() and path.suffix in ['.py', '.ipynb', '.txt', '.md', '.json', '.c', '.cpp', '.h']:
                file_size = path.stat().st_size
                if current_size + file_size > 10 * 1024 * 1024:
                    print("\n\033[1;31m[!] 10MB Limit Reached. Skipping remaining files.\033[0m")
                    break
                try:
                    files_data[str(path)] = path.read_text(encoding='utf-8')
                    current_size += file_size
                except: continue

        if not files_data: return

        try:
            # --- CTO FIX: USE SIGNED HEADERS ---
            # We don't need to manually load keys here; _signed_headers does it.
            # We get the public key from the identity file to send in the body for the folder name.
            identity = ClientIdentity()
            sk = identity.load_or_create()
            pub_key = binascii.hexlify(sk.verify_key.encode()).decode()
            
            response = await self.client.post(
                f"{BASE_URL}/sync/push",
                json={
                    "student_id": pub_key, # Send ID so server knows where to save
                    "files": files_data
                },
                headers=self._signed_headers("/sync/push") # <--- CRITICAL AUTH HEADER
            )
            if response.status_code == 200:
                print("\n\033[1;32m[LUM] Cloud Vault Synchronized Successfully.\033[0m")
        except Exception:
            pass
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
    # def run_manufactured_notebook(self, nb_path):
    #     print(f"[*] Executing cells in {nb_path} to capture live outputs...")
    #     with open(nb_path, "r") as f:
    #         nb = json.load(f)

    #     # Shared namespace for all cells (variables persist from cell 1 to cell N)
    #     namespace = {}

    #     for cell in nb["cells"]:
    #         if cell["cell_type"] == "code":
    #             code = "".join(cell["source"])
                
    #             # Redirect stdout to capture the result
    #             import io
    #             from contextlib import redirect_stdout
    #             f = io.StringIO()
    #             try:
    #                 with redirect_stdout(f):
    #                     exec(code, namespace)
    #                 output_text = f.getvalue()
                    
    #                 # Store the actual output in the notebook JSON format
    #                 cell["outputs"] = [{
    #                     "name": "stdout",
    #                     "output_type": "stream",
    #                     "text": [output_text]
    #                 }]
    #                 cell["execution_count"] = 1
    #             except Exception as e:
    #                 cell["outputs"] = [{
    #                     "name": "stderr",
    #                     "output_type": "stream",
    #                     "text": [f"Execution Error: {str(e)}"]
    #                 }]

    #     # Save the notebook with the new outputs
    #     with open(nb_path, "w") as f:
    #         json.dump(nb, f, indent=2)
    #     print(f"[✔] Execution complete. Outputs injected into {nb_path}")
    def get_synced_ts(self):
        return str(int(time.time() + self.time_offset))
    async def generate_notebook(self, input_file, output_file):
        cmd = "format"
        if not Path(input_file).exists():
            print(f"[!] Input file {input_file} not found.")
            return
        content = Path(input_file).read_text()
        print(f"[*] Reformatting {input_file} via Lum Engine...")
            
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
                        print(f"[✔] {input_file} is now formatted for injection.")
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
                        "source": [f"> **{idx}. {task['filename']}**: {task['question']}"]
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

    async def run_ai_task(self, mode, version, input_text):
        payload = {
            "mode": mode,
            "version": version,
            "language": "english",
            "input": input_text
        }

        path = "/ai/execute"
        print(f"[*] Lum is thinking (Mode: {mode})...")

        try:
            # 1. Attempt the request with current signed headers
            response = await self.client.post(
                f"{BASE_URL}{path}",
                json=payload,
                headers=self._signed_headers(path)
            )

            # 2. If 401, refresh token and RE-SIGN the request
            if response.status_code == 401:
                refreshed = await self.refresh_token()
                if not refreshed:
                    print("[!] Session expired. Please login again.")
                    return None

                # Crucial: Call self._signed_headers again to get the NEW token and NEW timestamp
                response = await self.client.post(
                    f"{BASE_URL}{path}",
                    json=payload,
                    headers=self._signed_headers(path)
                )

            # 3. Handle the response
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return response.content
                
                data = response.json()
                return self.clean_response(data.get("output"))

            # 4. Handle errors
            print(f"[!] Server Error {response.status_code}: {response.text}")
            return None

        except Exception as e:
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
        self.idle_worker.notify_activity()
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
            filename = args[1]
            if os.path.exists(filename):
                content = Path(filename).read_text()
                # Uses 'fix' mode to get pure code back
                result = await self.run_ai_task("fix", "standard", content)
                if result:
                    Path(filename).write_text(result)
                    print(f"[✔] {filename} has been fixed and updated.")
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

        # 3. WRITE: lum write "prompt" <filename>
        elif cmd == "write":
            if len(args) > 2:
                prompt, filename = args[1], args[2]
                result = await self.run_ai_task("write", "standard", prompt)
                if result:
                    Path(filename).write_text(result)
                    print(f"[✔] Code written to {filename}")
            else:
                print("[!] Usage: lum write \"prompt\" <filename>")

        # 4. ASK: lum ask "question"
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
        elif cmd == "inject":
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
            print("[*] Manual Sync Requested...")
            await self.push_to_cloud()
            return
        elif cmd == "chat":
            if len(args) > 2:
                await self.start_chat(args[1], args[2])
            else:
                print("[!] Usage: lum chat <channel_name> <password>")
        # 5. FC (Flowchart): lum fc <filename>
        elif cmd == "fc":
            filename = args[1]
            if os.path.exists(filename):
                content = Path(filename).read_text()
                # Returns BYTES (PNG image)
                result_bytes = await self.run_ai_task("fc", "standard", content)
                
                if result_bytes:
                    out_img = f"{Path(filename).stem}_fc.png"
                    with open(out_img, "wb") as f:
                        f.write(result_bytes)
                    print(f"[✔] ISO Flowchart generated: {out_img}")
            else:
                print(f"[!] File {filename} not found.")

        elif cmd == "stcht":
            print(f"[*] Secure Tunnel to {args[1]} initialized (Feature Pending)...")

    def show_help(self):
        print("""
Lum CLI - AI Co-Pilot
---------------------
  lum ask "question"            : Ask a general coding question
  lum write "task" <file>       : Write code from scratch to a file
  lum fix <file>                : Fix bugs in an existing file (in-place)
  lum algo <file>               : Extract algorithm logic from code
  lum fc <file>                 : Generate an ISO Flowchart image (PNG)
  lum chat <room> <pass>        : Join a real-time private study room
  lum stream <file>             : Start streaming your typing live
  lum follow <user>             : Watch a student/teacher code in real-time
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
    asyncio.run(main())