import sys
import os
import httpx
import asyncio
import json
from pathlib import Path

BASE_URL = "https://test-termial.onrender.com"

class LumCLI:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def run_ai_task(self, mode, version, input_text):
        # This payload now matches your PROMPTS dict keys exactly
        payload = {
            "mode": mode,         # Must be 'ask', 'algorithm', or 'fix'
            "version": version,   # Must be 'short', 'long', 'exam', or 'standard'
            "language": "english",
            "input": input_text
        }
        
        print(f"[*] Lum is thinking (Mode: {mode}, Version: {version})...")
        
        # Using the full path you verified
        endpoint = f"{BASE_URL}/ai/execute"
        
        try:
            response = await self.client.post(endpoint, json=payload)
            
            if response.status_code == 200:
                return response.json().get("output")
            else:
                # Fallback to root if /ai/execute fails
                alt_response = await self.client.post(f"{BASE_URL}/", json=payload)
                if alt_response.status_code == 200:
                    return alt_response.json().get("output")
                
                print(f"[!] Error: {response.text}")
                return None
        except Exception as e:
            print(f"[!] Connection failed: {str(e)}")
            return None

    async def handle_command(self, args):
        if len(args) < 2:
            self.show_help()
            return

        cmd = args[0]
        
        # 1. FIX command -> Maps to PROMPTS['fix']['standard']
        if cmd == "fix":
            filename = args[1]
            if os.path.exists(filename):
                content = Path(filename).read_text()
                result = await self.run_ai_task("fix", "standard", content)
                if result:
                    Path(filename).write_text(result)
                    print(f"[✔] {filename} has been updated with the fix.")
            else:
                print(f"[!] File {filename} not found.")

        # 2. ALGO command -> Maps to PROMPTS['algorithm']['standard']
        elif cmd == "algo":
            filename = args[1]
            if os.path.exists(filename):
                content = Path(filename).read_text()
                result = await self.run_ai_task("algorithm", "standard", content)
                if result:
                    new_file = f"{Path(filename).stem}_algo.txt"
                    Path(new_file).write_text(result)
                    print(f"[✔] Algorithm saved to {new_file}")

        # 3. WRITE/ASK command -> Maps to PROMPTS['ask']['long']
        elif cmd == "write" or cmd == "ask":
            if cmd == "write" and len(args) > 2:
                question = args[1]
                filename = args[2]
                result = await self.run_ai_task("ask", "long", question)
                if result:
                    Path(filename).write_text(result)
                    print(f"[✔] Code written to {filename}")
            else:
                question = args[1]
                result = await self.run_ai_task("ask", "short", question)
                if result:
                    print(f"\n[Lum]: {result}")

        elif cmd == "stcht":
            print(f"[*] Connecting to {args[1]}...")

    def show_help(self):
        print("Usage: lum <fix|algo|write|ask> <target>")

async def main():
    lum = LumCLI()
    if len(sys.argv) > 1:
        # Handling the 'lum' alias prefix correctly
        start_idx = 2 if sys.argv[1] == "lum" else 1
        await lum.handle_command(sys.argv[start_idx:])
    else:
        lum.show_help()

if __name__ == "__main__":
    asyncio.run(main())