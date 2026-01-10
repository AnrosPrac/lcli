import random
import time
import asyncio
import sys
import json

class LogicBattle:
    def __init__(self, cli_instance=None):
        self.score = 0
        self.lum = cli_instance
        
    async def fetch_ai_challenge(self, level):
        if self.lum:
            try:
                raw_data = await self.lum.run_ai_task("game_logic", "standard", level=level)
                clean_data = raw_data.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_data)
            except:
                return self.generate_fallback(level)
        return self.generate_fallback(level)

    def generate_fallback(self, level):
        a, b = random.choice([True, False]), random.choice([True, False])
        ops = ["and", "or", "==", "!="]
        op = random.choice(ops)
        expr = f"({a} {op} {b})"
        return {"expr": expr, "answer": eval(expr.lower())}

    async def get_input_with_timeout(self, timeout):
        if sys.platform == 'win32':
            import msvcrt
            start_time = time.time()
            input_str = ""
            while time.time() - start_time < timeout:
                if msvcrt.kbhit():
                    char = msvcrt.getche().decode('utf-8').lower()
                    if char in ['t', 'f']:
                        print()
                        return char
            return None
        else:
            import select
            i_ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if i_ready:
                return sys.stdin.readline().strip().lower()
            return None

    async def play(self):
        print("\033[H\033[J") 
        print("\033[1;35m=== LUM ARCADE: LOGIC BATTLE ===\033[0m")
        print("Evaluate the boolean expression. Quick response required!\n")
        
        try:
            for i in range(1, 11):
                challenge = await self.fetch_ai_challenge(i)
                expr, answer = challenge['expr'], challenge['answer']
                
                print(f"\033[1;33mROUND {i}/10: \033[0m {expr}")
                print("Your Answer (t/f): ", end="", flush=True)
                
                user_input = await self.get_input_with_timeout(4.0)
                
                if user_input:
                    correct = (user_input == 't' and answer) or (user_input == 'f' and not answer)
                    if correct:
                        print(f"\033[92m✔ COMPILED SUCCESSFULLY\033[0m\n")
                        self.score += 10
                    else:
                        print(f"\033[91m✘ RUNTIME ERROR: Expected {answer}\033[0m\n")
                else:
                    print(f"\n\033[91m✘ TIMEOUT: CPU Cycle exceeded.\033[0m (Answer: {answer})\n")

            print(f"\033[1;32mSESSION FINISHED! Final Dev Score: {self.score}/100\033[0m")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n\033[90mKilling process... Arcade closed.\033[0m")

async def start_logic_game(cli_instance=None):
    game = LogicBattle(cli_instance)
    await game.play()