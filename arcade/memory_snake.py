import curses
import random
import time

def start_overflow_game():
    def main(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.timeout(100)
        sh, sw = stdscr.getmaxyx()
        
        snake_x = sw // 4
        snake_y = sh // 2
        
        snake = [
            [snake_y, snake_x],
            [snake_y, snake_x - 1],
            [snake_y, snake_x - 2]
        ]
        
        food = [sh // 2, sw // 2]
        key = curses.KEY_RIGHT
        score = 0
        
        while True:
            next_key = stdscr.getch()
            if next_key != -1:
                if next_key in [curses.KEY_DOWN, curses.KEY_UP, curses.KEY_LEFT, curses.KEY_RIGHT]:
                    if not (key == curses.KEY_UP and next_key == curses.KEY_DOWN) and \
                       not (key == curses.KEY_DOWN and next_key == curses.KEY_UP) and \
                       not (key == curses.KEY_LEFT and next_key == curses.KEY_RIGHT) and \
                       not (key == curses.KEY_RIGHT and next_key == curses.KEY_LEFT):
                        key = next_key

            if snake[0][0] in [0, sh-1] or snake[0][1] in [0, sw-1] or snake[0] in snake[1:]:
                break
                
            new_head = [snake[0][0], snake[0][1]]
            
            if key == curses.KEY_DOWN: new_head[0] += 1
            if key == curses.KEY_UP: new_head[0] -= 1
            if key == curses.KEY_LEFT: new_head[1] -= 1
            if key == curses.KEY_RIGHT: new_head[1] += 1
            
            snake.insert(0, new_head)
            
            if snake[0][0] == food[0] and (snake[0][1] <= food[1] <= snake[0][1] + 5):
                score += 1
                food = None
                while food is None:
                    nf = [random.randint(1, sh-2), random.randint(1, sw-7)]
                    food = nf if nf not in snake else None
                stdscr.addstr(0, 2, f" [ Malloc Success: Score {score*10} ] ", curses.A_REVERSE)
            else:
                tail = snake.pop()
                stdscr.addstr(tail[0], tail[1], "  ")

            try:
                stdscr.addstr(food[0], food[1], "0xDATA", curses.A_BOLD)
                for i, pos in enumerate(snake):
                    char = "0x" if i == 0 else ".."
                    stdscr.addstr(pos[0], pos[1], char)
            except:
                pass
            
            stdscr.refresh()

        stdscr.nodelay(0)
        stdscr.clear()
        msg = f" SEGMENTATION FAULT: Memory Overflow at {hex(id(snake))} "
        stdscr.addstr(sh//2, (sw-len(msg))//2, msg, curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(sh//2 + 1, (sw-20)//2, f"Final Score: {score*10}")
        stdscr.refresh()
        time.sleep(2)
        stdscr.getch()

    curses.wrapper(main)

if __name__ == "__main__":
    start_overflow_game()