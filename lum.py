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
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_URL = "https://test-termial.onrender.com"  # Ensure this is your live URL


class CodeWatcher(FileSystemEventHandler):
    def __init__(self, username, filename, ws, loop):
        self.username = username
        self.filename = filename
        self.ws = ws
        self.loop = loop

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(self.filename):
            try:
                content = Path(self.filename).read_text()
                asyncio.run_coroutine_threadsafe(
                    self.ws.send(json.dumps({"code": content, "file": self.filename})), 
                    self.loop
                )
            except Exception as e:
                print(f"Update failed: {e}")

class StreamHandler:
    async def start_broadcast(self, filename):
        username = getpass.getuser()
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/source/{username}"
        
        async with websockets.connect(uri) as ws:
            print(f"[*] Live Stream Active: Anyone can run 'lum follow {username}'")
            loop = asyncio.get_running_loop()
            event_handler = CodeWatcher(username, filename, ws, loop)
            observer = Observer()
            observer.schedule(event_handler, path=".", recursive=False)
            observer.start()
            try:
                while True: await asyncio.sleep(1)
            except: observer.stop()
            observer.join()

    async def follow_user(self, target_user):
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/watch/{target_user}"
        async with websockets.connect(uri) as ws:
            os.system('clear' if os.name == 'posix' else 'cls')
            print(f"--- SPECTATING: {target_user} --- (Ctrl+C to stop)")
            try:
                while True:
                    data = json.loads(await ws.recv())
                    if data["type"] == "live_code":
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print(f"--- FILE: {data['file']} | USER: {target_user} ---\n")
                        print(data["content"])
            except: print(f"\n[!] Stream ended.")
class LumCLI:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0) # Increased timeout for Graphviz rendering

    def clean_response(self, text):
        """Removes Markdown code blocks (```c, ```json, etc.) from the response."""
        if not isinstance(text, str): return text
        # Remove start/end code fences
        cleaned = re.sub(r"```[a-zA-Z]*\n|```", "", text)
        return cleaned.strip()

    async def run_ai_task(self, mode, version, input_text):
        payload = {
            "mode": mode,
            "version": version,
            "language": "english",
            "input": input_text
        }
        
        print(f"[*] Lum is thinking (Mode: {mode})...")
        endpoint = f"{BASE_URL}/ai/execute"
        
        try:
            response = await self.client.post(endpoint, json=payload)
            
            if response.status_code == 200:
                # Content-Type Check: Is it an Image (Flowchart) or Text (JSON)?
                content_type = response.headers.get("content-type", "")
                
                if "image" in content_type:
                    # Return raw bytes for images
                    return response.content
                else:
                    # Return cleaned text for code/answers
                    raw_text = response.json().get("output")
                    return self.clean_response(raw_text)
            else:
                print(f"[!] Server Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"[!] Connection failed: {str(e)}")
            return None


    async def start_chat(self, channel, password):
        username = getpass.getuser()
        # Convert https to wss for the socket connection
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/chat/{channel}/{password}/{username}"
        
        try:
            async with websockets.connect(uri) as ws:
                os.system('clear' if os.name == 'posix' else 'cls')
                print(f"--- Channel: {channel} | User: {username} ---")
                print("[!] Type message and hit Enter. Type '/exit' to quit.\n")

                async def receive():
                    while True:
                        try:
                            msg_raw = await ws.recv()
                            data = json.loads(msg_raw)
                            # Blue for users, Grey for system
                            color = "\033[94m" if data["type"] == "chat" else "\033[90m"
                            print(f"\r{color}[{data['user']}]:\033[0m {data['msg']}\n\033[92m> \033[0m", end="", flush=True)
                        except: break

                async def send():
                    while True:
                        # Standard input loop
                        msg = await asyncio.get_event_loop().run_in_executor(None, input, "\033[92m> \033[0m")
                        if msg.lower() == "/exit":
                            await ws.close()
                            break
                        await ws.send(msg)

                await asyncio.gather(receive(), send())
        except Exception as e:
            print(f"[!] Chat disconnected: {e}")
    async def handle_command(self, args):
        if len(args) < 2:
            self.show_help()
            return

        cmd = args[0]
        
        # 1. FIX: lum fix <filename>
        if cmd == "fix":
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

        # 7. STREAM: lum stream <file>
        elif cmd == "stream":
            if len(args) > 1:
                handler = StreamHandler()
                await handler.start_broadcast(args[1])
            else:
                print("[!] Usage: lum stream <filename>")

        # 8. FOLLOW: lum follow <user>
        elif cmd == "follow":
            if len(args) > 1:
                handler = StreamHandler()
                await handler.follow_user(args[1])
            else:
                print("[!] Usage: lum follow <username>")
        # 6. CHAT: lum chat <channel> <password>
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