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


BASE_URL = "https://test-termial.onrender.com"  # Ensure this is your live URL



class StreamHandler:
    async def start_broadcast(self, filename):
        username = getpass.getuser()
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/source/{username}"
        
        # Cross-version compatible connection
        try:
            ws_conn = websockets.connect(uri, extra_headers={"Origin": BASE_URL})
        except TypeError:
            ws_conn = websockets.connect(uri, additional_headers={"Origin": BASE_URL})

        async with ws_conn as ws:
            print(f"[*] ULTRA-LOW LATENCY STREAM: Active")
            print(f"[*] Spectators can run: lum follow {username}")
            last_content = ""
            try:
                while True:
                    if os.path.exists(filename):
                        content = Path(filename).read_text()
                        if content != last_content:
                            await ws.send(json.dumps({
                                "code": content, 
                                "file": filename,
                                "ts": time.time() 
                            }))
                            last_content = content
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"\n[!] Stream stopped: {e}")

    async def follow_user(self, target_user):
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        uri = f"{ws_url}/stream/watch/{target_user}"
        
        # Use a dictionary to dynamically pick the right keyword for your version
        params = {"Origin": BASE_URL}
        
        # This is the 'Master Fix': 
        # It checks if the library is the new version (additional_headers) 
        # or old (extra_headers) before connecting.
        if hasattr(websockets, "connect"):
            try:
                # Try the modern 3.11+ way first
                ws = await websockets.connect(uri, additional_headers=params)
            except TypeError:
                # Fallback to the old way
                ws = await websockets.connect(uri, extra_headers=params)

        async with ws:
            os.system('clear' if os.name == 'posix' else 'cls')
            print(f"--- SPECTATING: {target_user} --- (Ctrl+C to stop)")
            try:
                while True:
                    raw_data = await ws.recv()
                    data = json.loads(raw_data)
                    if data.get("type") == "live_code":
                        latency = (time.time() - data.get("ts", time.time())) * 1000
                        speed_color = "\033[92m" if latency < 200 else "\033[93m"
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print(f"--- FILE: {data['file']} | USER: {target_user} | SPEED: {speed_color}{latency:.0f}ms\033[0m ---")
                        print("-" * 60 + "\n" + data["content"] + "\n" + "-" * 60)
            except Exception as e: 
                print(f"\n[!] Stream ended: {e}")
class LumCLI:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)

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
                    
                    print(f"[*] Comparing logic flow...")
                    try:
                        response = await self.client.post(f"{BASE_URL}/ai/execute", json=payload)
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
                handler = StreamHandler()
                await handler.start_broadcast(args[1])
            else:
                print("[!] Usage: lum stream <filename>")

                # Add this inside the handle_command method in LumCLI class
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
            try:
                response = await self.client.post(endpoint, json={"text_content": content})
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
                    timeout=180.0 # High timeout for batch generation
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
            try:
                response = await self.client.post(endpoint, json={"text_content": content})
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
                handler = StreamHandler()
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