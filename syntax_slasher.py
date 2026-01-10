import time
import asyncio
import json

class SyntaxSlasher:
    def __init__(self, cli_instance):
        self.lum = cli_instance
        self.score = 0

    def clean_res(self, text):
        return text.replace("```json", "").replace("```", "").strip()

    async def play(self):
        print("\033[H\033[J")
        print("\033[1;36m=== LUM ARCADE: SYNTAX SLASHER ===\033[0m")
        lang = input("Select Language (default: C++): ") or "C++"
        print(f"\nInitialising kernel debugger for {lang}...")
        
        try:
            for r_num in range(1, 6):
                print(f"\033[90m[*] Round {r_num}: Compiling challenge via AI...\033[0m")
                
                raw_data = await self.lum.run_ai_task("game_syntax", "standard", language=lang)
                challenge = json.loads(self.clean_res(raw_data))
                
                print("\033[H\033[J")
                print(f"--- ROUND {r_num} | SCORE: {self.score} | LANG: {lang} ---")
                
                lines = challenge['code'].strip().split('\n')
                for idx, line in enumerate(lines):
                    print(f"\033[90m{idx + 1:2} |\033[0m {line}")
                
                print("-" * 45)
                start_t = time.time()
                ans = input("\033[1;33mEnter Buggy Line Number:\033[0m ")
                
                if ans.isdigit() and int(ans) == challenge['buggy_line']:
                    elapsed = time.time() - start_t
                    points = max(10, int(100 - (elapsed * 2)))
                    self.score += points
                    print(f"\033[92m✔ BUG SLASHED! +{points} pts ({elapsed:.1f}s)\033[0m")
                else:
                    print(f"\033[91m✘ SYSTEM CRASHED!\033[0m")
                    print(f"Line {challenge['buggy_line']} was the culprit.")
                    print(f"Root Cause: {challenge['explanation']}")
                
                print("\033[90mNext round in 4 seconds...\033[0m")
                time.sleep(4)

            print(f"\n\033[1;32mDEBUGGING SESSION COMPLETE! Final Score: {self.score}\033[0m")
            time.sleep(2)
        except Exception as e:
            print(f"\033[91m[!] Kernel Panic (Game Error): {e}\033[0m")
            time.sleep(2)

async def start_syntax_game(cli_instance):
    game = SyntaxSlasher(cli_instance)
    await game.play()