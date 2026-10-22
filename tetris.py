"""Tetris - single board, with background image + bloom. pip install pygame"""
import pygame, random, sys
from pygame.locals import *

W, H, B, COLS, ROWS = 600, 700, 32, 10, 20
BX, BY = (W - COLS * B) // 2, (H - ROWS * B) // 2
GOLD = (255, 220, 0)
PIECES = [  # (cells around a pivot, colour)
    ([(-1, 0), (0, 0), (1, 0), (2, 0)], (0, 220, 255)),    # I
    ([(0, 0), (1, 0), (0, 1), (1, 1)], GOLD),              # O
    ([(-1, 0), (0, 0), (1, 0), (0, -1)], (200, 0, 255)),   # T
    ([(-1, 0), (0, 0), (0, -1), (1, -1)], (0, 255, 80)),   # S
    ([(-1, -1), (0, -1), (0, 0), (1, 0)], (255, 40, 40)),  # Z
    ([(-1, -1), (-1, 0), (0, 0), (1, 0)], (60, 80, 255)),  # J
    ([(1, -1), (-1, 0), (0, 0), (1, 0)], (255, 140, 0)),   # L
]
MOVES = {K_LEFT: (-1, 0), K_RIGHT: (1, 0), K_DOWN: (0, 1)}


def fits(cells, px, py, grid):
    return all(0 <= px + x < COLS and py + y < ROWS and (px + x, py + y) not in grid for x, y in cells)


class Game:
    def __init__(self):
        self.grid, self.score, self.lines, self.over = {}, 0, 0, False
        self.next = random.choice(PIECES)
        self.spawn()

    def spawn(self):
        (self.cells, self.color), self.next = self.next, random.choice(PIECES)
        self.x, self.y = 4, 1
        self.over = not fits(self.cells, self.x, self.y, self.grid)

    def move(self, dx, dy):
        ok = fits(self.cells, self.x + dx, self.y + dy, self.grid)
        if ok:
            self.x, self.y = self.x + dx, self.y + dy
        return ok

    def rotate(self):
        if self.color == GOLD:
            return
        c = [(-y, x) for x, y in self.cells]
        for k in (0, -1, 1, -2, 2):  # simple wall kicks
            if fits(c, self.x + k, self.y, self.grid):
                self.cells, self.x = c, self.x + k
                return

    def step(self):  # gravity / soft drop
        if not self.move(0, 1):
            self.lock()

    def hard_drop(self):
        while self.move(0, 1):
            pass
        self.lock()

    def lock(self):
        for x, y in self.cells:
            self.grid[(self.x + x, self.y + y)] = self.color
        full = [r for r in range(ROWS) if all((c, r) in self.grid for c in range(COLS))]
        self.grid = {(x, y + sum(f > y for f in full)): c for (x, y), c in self.grid.items() if y not in full}
        self.lines += len(full)
        self.score += [0, 100, 300, 500, 800][len(full)]
        self.spawn()

    def ghost_y(self):
        y = self.y
        while fits(self.cells, self.x, y + 1, self.grid):
            y += 1
        return y


def block(s, c, x, y):
    r = pygame.Rect(x + 1, y + 1, B - 2, B - 2)
    pygame.draw.rect(s, [min(v + 30, 255) for v in c], r)
    pygame.draw.rect(s, [max(v - 40, 0) for v in c], r.inflate(-12, -12).move(4, 4))
    pygame.draw.line(s, (255, 255, 255), r.topleft, r.topright)
    pygame.draw.line(s, (255, 255, 255), r.topleft, r.bottomleft)


def draw(screen, g, bg, bright, font, big):
    screen.blit(bg, (0, 0)) if bg else screen.fill((6, 6, 12))
    dark = pygame.Surface((W, H)); dark.set_alpha(160); screen.blit(dark, (0, 0))
    board = pygame.Rect(BX, BY, COLS * B, ROWS * B)
    pygame.draw.rect(screen, (8, 8, 16), board)
    for i in range(COLS + 1):
        pygame.draw.line(screen, (22, 22, 35), (BX + i * B, BY), (BX + i * B, BY + ROWS * B))
    for i in range(ROWS + 1):
        pygame.draw.line(screen, (22, 22, 35), (BX, BY + i * B), (BX + COLS * B, BY + i * B))
    for t, col in [(6, (40, 40, 80)), (3, (80, 80, 160)), (1, (140, 140, 255))]:
        pygame.draw.rect(screen, col, board.inflate(t * 2, t * 2), t)

    gy = g.ghost_y()  # ghost piece
    for x, y in g.cells:
        r = pygame.Rect(BX + (g.x + x) * B + 1, BY + (gy + y) * B + 1, B - 2, B - 2)
        if gy + y >= 0:
            pygame.draw.rect(screen, [v // 2 for v in g.color], r, 1)

    blocks = [(x, y, c) for (x, y), c in g.grid.items()] + [(g.x + x, g.y + y, g.color) for x, y in g.cells]
    bright.fill((0, 0, 0))
    for x, y, c in blocks:
        if y >= 0:
            block(screen, c, BX + x * B, BY + y * B)
            block(bright, c, BX + x * B, BY + y * B)
    for d in (6, 16):  # bloom: downscale + upscale = cheap blur, added on top
        small = pygame.transform.smoothscale(bright, (W // d, H // d))
        screen.blit(pygame.transform.smoothscale(small, (W, H)), (0, 0), special_flags=BLEND_RGB_ADD)

    # UI drawn after bloom so text stays crisp
    screen.blit(big.render("TETRIS", True, (200, 200, 255)), (W // 2 - 70, 14))
    for i, t in enumerate((f"SCORE {g.score}", f"LINES {g.lines}", f"LVL   {g.lines // 10 + 1}")):
        screen.blit(font.render(t, True, (180, 180, 230)), (BX + COLS * B + 25, BY + 130 + i * 30))
    screen.blit(font.render("NEXT", True, (120, 120, 200)), (BX + COLS * B + 25, BY + 20))
    for x, y in g.next[0]:
        block(screen, g.next[1], BX + COLS * B + 55 + x * B, BY + 70 + y * B)
    if g.over:
        msg = big.render("GAME OVER - R to restart", True, (255, 60, 60))
        screen.blit(msg, (W // 2 - msg.get_width() // 2, H // 2))


def main():
    pygame.init()
    pygame.key.set_repeat(150, 50)
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Tetris")
    try:
        bg = pygame.transform.scale(pygame.image.load("hehe.jpeg").convert(), (W, H))
    except (pygame.error, FileNotFoundError):
        bg = None
    font, big = pygame.font.SysFont("Consolas", 22), pygame.font.SysFont("Consolas", 40, bold=True)
    bright, clock, g, timer, held = pygame.Surface((W, H)), pygame.time.Clock(), Game(), 0, set()

    while True:
        timer += clock.tick(60)
        for e in pygame.event.get():
            if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                pygame.quit(); sys.exit()
            if e.type == KEYUP:
                held.discard(e.key)
            if e.type == KEYDOWN:
                first = e.key not in held  # ignore key-repeat for one-shot actions
                held.add(e.key)
                if e.key == K_r:
                    g = Game()
                elif g.over:
                    continue
                elif e.key in MOVES:
                    g.move(*MOVES[e.key]) if e.key != K_DOWN else g.step()
                elif first and e.key == K_UP:
                    g.rotate()
                elif first and e.key == K_SPACE:
                    g.hard_drop()
        if not g.over and timer > max(80, 550 - 40 * (g.lines // 10)):
            timer = 0
            g.step()
        draw(screen, g, bg, bright, font, big)
        pygame.display.flip()


if __name__ == "__main__":
    main()