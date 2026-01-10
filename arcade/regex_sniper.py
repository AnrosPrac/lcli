import re
import time
import random
import asyncio
import json

class RegexSniper:
    def __init__(self, cli_instance=None):
        self.score = 0
        self.lum = cli_instance
        # Fallback challenges for offline mode
        self.fallbacks = [
            (r"^\d{3}$", ["123", "abc", "12a", "99"]),
            (r"^[a-z]+$", ["hello", "H3llo", "hi!", "123"]),
            (r"\.com$", ["google.com", "google.org", "com.google", "google"]),
            (r"^#[0-9a-fA-F]{6}$", ["#ffffff", "#ff12", "f12345", "#gggggg"]),
            (r"^[A-Z]{2,4}$", ["API", "a", "PYTHON", "123"]),
            (r"^\(\d{3}\)$", ["(123)", "123", "(abc)", "(12)"])
        ]

    async def fetch_ai_challenge(self):
        """Fetches a new regex puzzle from the AI or falls back to local data."""
        if self.lum:
            try:
                # Intentionally not passing {level} as regex is standard difficulty
                raw = await self.lum.run_ai_task("game_regex", "standard")
                clean = raw.replace("```json", "").replace("```", "").strip()
                return json.loads(clean)
            except Exception:
                pass # Silently fail back to local patterns
        
        p, o = random.choice(self.fallbacks)
        return {"pattern": p, "options": o}

    async def play(self):
        print("\033[H\033[J")
        print("\033[1;31m=== LUM ARCADE: REGEX SNIPER ===\033[0m")
        print("Target the string that matches the Regex pattern!\n")

        try:
            for round_num in range(1, 7):
                # 1. Fetch Data
                challenge = await self.fetch_ai_challenge()
                pattern = challenge['pattern']
                options = challenge['options']
                
                # 2. Shuffle ensures the answer isn't always in the same spot
                random.shuffle(options)
                
                # 3. Display Interface
                print(f"ROUND {round_num}/6: TARGET -> \033[1;33m{pattern}\033[0m")
                for i, opt in enumerate(options):
                    print(f" [{i+1}] {opt}")
                
                # 4. User Input Phase
                start_t = time.time()
                choice = input("\nSniper Choice (1-4): ").strip()
                elapsed = time.time() - start_t
                
                # 5. Validation Logic (Using local regex engine for 100% accuracy)
                if choice.isdigit() and 1 <= int(choice) <= len(options):
                    selected = options[int(choice)-1]
                    
                    # We re-compile the pattern to ensure validity
                    if re.match(pattern, selected):
                        # Speed Bonus: Faster answers get more points
                        bonus = max(5, int(20 - elapsed))
                        points = 20 + bonus
                        self.score += points
                        print(f"\033[92m✔ TARGET ELIMINATED! +{points} pts ({elapsed:.1f}s)\033[0m\n")
                    else:
                        print(f"\033[91m✘ MISFIRE! '{selected}' failed validation.\033[0m\n")
                else:
                    print("\033[91m✘ ABORTED: Invalid input.\033[0m\n")
                
                time.sleep(1.5)

            print(f"\033[1;32mMISSION COMPLETE! Final Score: {self.score}/200\033[0m")
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n\033[90mPowering down sniper scope...\033[0m")

async def start_regex_game(cli_instance=None):
    game = RegexSniper(cli_instance)
    await game.play()