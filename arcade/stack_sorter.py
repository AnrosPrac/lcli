import time
import random

class StackSorter:
    def __init__(self):
        self.rax = [random.randint(10, 99) for _ in range(4)]
        self.rbx = []
        self.rcx = []
        self.target = sorted(self.rax, reverse=True)
        self.moves = 0

    def display(self, message=""):
        print("\033[H\033[J")
        print("\033[1;34m=== LUM ARCADE: STACK SORTER ===\033[0m")
        print(f"Goal: Sort RAX into RBX (Descending Order: {self.target})")
        print(f"Moves executed: {self.moves}")
        if message:
            print(f"\033[1;33mSTATUS: {message}\033[0m")
        print("\n" + "━" * 40)
        
        for name, stack in [("RAX", self.rax), ("RBX", self.rbx), ("RCX", self.rcx)]:
            stack_view = " | ".join(map(str, stack))
            ptr = " <-- TOP" if stack else ""
            print(f"\033[1;36m{name}:\033[0m [ {stack_view} ]{ptr}")
        
        print("━" * 40)
        print("\nCommands: \033[1;32mpush <src> <dest>\033[0m (e.g., push rax rbx)")
        print("Registers: rax, rbx, rcx | Exit: quit\n")

    def play(self):
        registers = {"rax": self.rax, "rbx": self.rbx, "rcx": self.rcx}
        last_msg = "Registers Initialized."
        
        try:
            while self.rbx != self.target:
                self.display(last_msg)
                user_input = input("asm> ").lower().split()
                
                if not user_input: continue
                if user_input[0] == "quit": break
                
                if len(user_input) == 3 and user_input[0] == "push":
                    src, dest = user_input[1], user_input[2]
                    if src in registers and dest in registers:
                        if registers[src]:
                            val = registers[src].pop()
                            registers[dest].append(val)
                            self.moves += 1
                            last_msg = f"Moved {val} from {src.upper()} to {dest.upper()}"
                        else:
                            last_msg = "\033[91mERROR: STACK UNDERFLOW\033[0m"
                    else:
                        last_msg = "\033[91mERROR: INVALID REGISTER\033[0m"
                else:
                    last_msg = "\033[91mERROR: INVALID OPCODE\033[0m"

            if self.rbx == self.target:
                self.display("STACK ALIGNMENT SECURED")
                print(f"\033[1;32mSUCCESS! System optimized in {self.moves} moves.\033[0m")
                time.sleep(3)
        except KeyboardInterrupt:
            print("\nShutting down register access...")

def start_stack_game():
    game = StackSorter()
    game.play()