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

    async def run_ai_task(self, mode, input_text, filename=None):
        payload = {
            "mode": mode,
            "version": "v1",
            "language": "english",
            "input": input_text
        }
        print(f"[*] Lum is thinking (Mode: {mode})...")
        response = await self.client.post(f"{BASE_URL}/execute", json=payload)
        
        if response.status_code == 200:
            return response.json().get("output")
        else:
            print(f"[!] Error: {response.text}")
            return None

    async def handle_command(self, args):
        if len(args) < 2:
            self.show_help()
            return

        cmd = args[0]
        
        # lum fix filename
        if cmd == "fix":
            filename = args[1]
            content = Path(filename).read_text()
            result = await self.run_ai_task("bug_fix", content)
            if result:
                Path(filename).write_text(result)
                print(f"[✔] {filename} has been fixed.")

        # lum algo filename
        elif cmd == "algo":
            filename = args[1]
            content = Path(filename).read_text()
            result = await self.run_ai_task("algorithm", content)
            if result:
                new_file = f"{Path(filename).stem}_algo.txt"
                Path(new_file).write_text(result)
                print(f"[✔] Algorithm saved to {new_file}")

        # lum write "question" filename
        elif cmd == "write":
            question = args[1]
            filename = args[2]
            result = await self.run_ai_task("coding", question)
            if result:
                Path(filename).write_text(result)
                print(f"[✔] Code written to {filename}")

        # lum explain filename
        elif cmd == "ask":
            filename = args[1]
            content = Path(filename).read_text()
            result = await self.run_ai_task("explanation", content)
            if result:
                print(f"\n--- Lum Explanation for {filename} ---\n{result}")

        # lum stcht (Start Chat)
        elif cmd == "stcht":
            target = args[1] # name or channelname
            # This triggers the TUI mode (Textual/WebSocket logic)
            print(f"[*] Connecting to {target} via Secure Tunnel...")
            # We will launch the Textual TUI here

        elif cmd == "ext":
            print("[*] Exiting Lum. Goodbye.")
            sys.exit(0)

    def show_help(self):
        print("Usage: lum <command> <target> [extra]")
        print("Commands: fix, algo, write, explain, stcht, ext")

async def main():
    lum = LumCLI()
    if len(sys.argv) > 1 and sys.argv[1] == "lum":
        await lum.handle_command(sys.argv[2:])
    else:
        lum.show_help()

if __name__ == "__main__":
    asyncio.run(main())