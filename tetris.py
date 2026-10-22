"""
TETRIS TEMPLATE
===============
A single-player Tetris with a background image and a glowing "bloom" effect.
Made as a starting point: change things, break things, make it your own!

Install:  pip install pygame
Run:      python tetris.py

Controls:
    LEFT / RIGHT  move the piece
    DOWN          soft drop (fall one row faster)
    UP            rotate
    SPACE         hard drop (instantly fall to the bottom)
    R             restart
    ESC           quit

How this file is organised (read it top to bottom):
    1. SETTINGS        - numbers and colours you can change easily
    2. PIECES          - the shapes of the blocks
    3. TetrisGame      - the rules of the game (no drawing here!)
    4. DRAWING         - functions that put things on the screen
    5. MAIN LOOP       - reads the keyboard, updates the game, draws
"""

import random
import sys

import pygame
from pygame.locals import (
    QUIT, KEYDOWN, KEYUP, BLEND_RGB_ADD,
    K_LEFT, K_RIGHT, K_DOWN, K_UP, K_SPACE, K_ESCAPE, K_r,
)


# =============================================================================
# 1. SETTINGS  -  try changing these first!
# =============================================================================

# --- Window and board size (in pixels / cells) ---
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 700
BLOCK_SIZE = 32            # width and height of one square, in pixels
BOARD_COLUMNS = 10         # how many squares wide the board is
BOARD_ROWS = 20            # how many squares tall the board is

# Top-left corner of the board on screen (this centers it in the window)
BOARD_LEFT = (WINDOW_WIDTH - BOARD_COLUMNS * BLOCK_SIZE) // 2
BOARD_TOP = (WINDOW_HEIGHT - BOARD_ROWS * BLOCK_SIZE) // 2

# --- Speed ---
START_FALL_DELAY_MS = 550  # milliseconds between automatic falls at level 1
SPEED_UP_PER_LEVEL_MS = 40 # each level makes the game this much faster
MIN_FALL_DELAY_MS = 80     # the game never gets faster than this
LINES_PER_LEVEL = 10

# --- Scoring: points for clearing 0, 1, 2, 3 or 4 lines at once ---
POINTS_FOR_LINES = [0, 100, 300, 500, 800]

# --- Look and feel ---
BACKGROUND_IMAGE = "hehe.jpeg"       # if this file is missing, a dark color is used
FALLBACK_BACKGROUND_COLOR = (6, 6, 12)
BACKGROUND_DARKNESS = 160            # 0 = image fully visible, 255 = fully black
BLOOM_BLUR_LEVELS = (6, 16)          # the glow effect. Bigger numbers = wider glow

BOARD_COLOR = (8, 8, 16)
GRID_LINE_COLOR = (22, 22, 35)
TEXT_COLOR = (180, 180, 230)
TITLE_COLOR = (200, 200, 255)
GAME_OVER_COLOR = (255, 60, 60)


# =============================================================================
# 2. PIECES  -  the seven Tetris shapes
# =============================================================================
# Each piece is a list of (x, y) offsets from a "pivot" square at (0, 0).
# x goes right, y goes DOWN (that is how screens work).
# For example the T piece is three squares in a row plus one on top:
#
#            (0,-1)
#     (-1,0) (0,0) (1,0)
#
# A piece is stored as (list_of_offsets, color).

COLOR_O_PIECE = (255, 220, 0)  # we remember this one because the O piece never rotates

PIECES = [
    ([(-1, 0), (0, 0), (1, 0), (2, 0)],   (0, 220, 255)),    # I  (cyan)
    ([(0, 0), (1, 0), (0, 1), (1, 1)],    COLOR_O_PIECE),    # O  (gold)
    ([(-1, 0), (0, 0), (1, 0), (0, -1)],  (200, 0, 255)),    # T  (violet)
    ([(-1, 0), (0, 0), (0, -1), (1, -1)], (0, 255, 80)),     # S  (green)
    ([(-1, -1), (0, -1), (0, 0), (1, 0)], (255, 40, 40)),    # Z  (red)
    ([(-1, -1), (-1, 0), (0, 0), (1, 0)], (60, 80, 255)),    # J  (blue)
    ([(1, -1), (-1, 0), (0, 0), (1, 0)],  (255, 140, 0)),    # L  (orange)
]


def piece_fits(offsets, piece_x, piece_y, locked_blocks):
    """
    Return True if a piece can sit at (piece_x, piece_y) on the board.

    It does NOT fit if any square would be:
      - outside the left/right walls,
      - below the floor,
      - on top of a square that is already locked in place.
    (Squares above the top of the board are allowed, so new pieces can spawn.)
    """
    for offset_x, offset_y in offsets:
        column = piece_x + offset_x
        row = piece_y + offset_y
        if column < 0 or column >= BOARD_COLUMNS:
            return False
        if row >= BOARD_ROWS:
            return False
        if (column, row) in locked_blocks:
            return False
    return True


# =============================================================================
# 3. THE GAME RULES
# =============================================================================

class TetrisGame:
    """
    Holds everything about one game of Tetris: the board, the falling piece,
    the score... and the rules for moving and clearing lines.

    This class never draws anything. It only keeps track of the game.
    Drawing is done separately (see section 4), which makes it easy to
    change how the game looks without breaking how it works.
    """

    def __init__(self):
        # locked_blocks remembers every square that has landed.
        # It is a dictionary:  (column, row) -> color
        self.locked_blocks = {}
        self.score = 0
        self.lines_cleared = 0
        self.is_game_over = False

        self.next_piece = random.choice(PIECES)
        self.spawn_next_piece()

    @property
    def level(self):
        """The level goes up every LINES_PER_LEVEL lines."""
        return self.lines_cleared // LINES_PER_LEVEL + 1

    @property
    def fall_delay_ms(self):
        """How many milliseconds pass between automatic falls."""
        delay = START_FALL_DELAY_MS - SPEED_UP_PER_LEVEL_MS * (self.level - 1)
        return max(MIN_FALL_DELAY_MS, delay)

    # ---- creating pieces ----------------------------------------------------

    def spawn_next_piece(self):
        """Make the 'next' piece the falling piece and pick a new 'next' one."""
        self.piece_offsets, self.piece_color = self.next_piece
        self.next_piece = random.choice(PIECES)
        self.piece_x = BOARD_COLUMNS // 2 - 1   # start near the middle
        self.piece_y = 1                        # start near the top

        # If a brand-new piece does not even fit, the board is full: game over.
        if not piece_fits(self.piece_offsets, self.piece_x, self.piece_y, self.locked_blocks):
            self.is_game_over = True

    # ---- moving the falling piece -------------------------------------------

    def try_move(self, change_x, change_y):
        """
        Move the piece by (change_x, change_y) if there is room.
        Returns True if it moved, False if something was in the way.
        """
        new_x = self.piece_x + change_x
        new_y = self.piece_y + change_y
        if piece_fits(self.piece_offsets, new_x, new_y, self.locked_blocks):
            self.piece_x = new_x
            self.piece_y = new_y
            return True
        return False

    def rotate(self):
        """Rotate the piece 90 degrees clockwise (if there is room)."""
        if self.piece_color == COLOR_O_PIECE:
            return  # the square piece looks the same rotated, so skip it

        # Rotating 90 degrees clockwise turns every offset (x, y) into (-y, x).
        rotated = [(-y, x) for x, y in self.piece_offsets]

        # "Wall kick": if the rotated piece hits a wall, try nudging it sideways.
        for nudge in (0, -1, 1, -2, 2):
            if piece_fits(rotated, self.piece_x + nudge, self.piece_y, self.locked_blocks):
                self.piece_offsets = rotated
                self.piece_x += nudge
                return

    def step_down(self):
        """Move the piece down one row. If it can't move, lock it in place."""
        if not self.try_move(0, 1):
            self.lock_piece()

    def hard_drop(self):
        """Drop the piece all the way down and lock it immediately."""
        while self.try_move(0, 1):
            pass
        self.lock_piece()

    def landing_row(self):
        """The row the piece would land on. Used to draw the 'ghost' outline."""
        row = self.piece_y
        while piece_fits(self.piece_offsets, self.piece_x, row + 1, self.locked_blocks):
            row += 1
        return row

    # ---- locking and clearing lines -----------------------------------------

    def lock_piece(self):
        """Turn the falling piece into permanent blocks, then clear full lines."""
        for offset_x, offset_y in self.piece_offsets:
            column = self.piece_x + offset_x
            row = self.piece_y + offset_y
            self.locked_blocks[(column, row)] = self.piece_color

        number_cleared = self.clear_full_rows()
        self.lines_cleared += number_cleared
        self.score += POINTS_FOR_LINES[number_cleared]

        self.spawn_next_piece()

    def clear_full_rows(self):
        """Remove every completely filled row. Returns how many were removed."""
        full_rows = []
        for row in range(BOARD_ROWS):
            row_is_full = all((column, row) in self.locked_blocks for column in range(BOARD_COLUMNS))
            if row_is_full:
                full_rows.append(row)

        # Build a new board: skip blocks in full rows, and move every other
        # block down by one row for each full row that was below it.
        new_blocks = {}
        for (column, row), color in self.locked_blocks.items():
            if row in full_rows:
                continue
            rows_cleared_below = sum(1 for full_row in full_rows if full_row > row)
            new_blocks[(column, row + rows_cleared_below)] = color
        self.locked_blocks = new_blocks

        return len(full_rows)


# =============================================================================
# 4. DRAWING
# =============================================================================
# Everything here only draws. None of it changes the game.

def board_to_pixels(column, row):
    """Convert a board position (column, row) to a screen position in pixels."""
    return BOARD_LEFT + column * BLOCK_SIZE, BOARD_TOP + row * BLOCK_SIZE


def draw_block(surface, color, pixel_x, pixel_y):
    """Draw one square: a light fill, a darker inner square, and white highlights."""
    lighter = [min(value + 30, 255) for value in color]
    darker = [max(value - 40, 0) for value in color]

    outer = pygame.Rect(pixel_x + 1, pixel_y + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2)
    inner = outer.inflate(-12, -12).move(4, 4)

    pygame.draw.rect(surface, lighter, outer)
    pygame.draw.rect(surface, darker, inner)
    pygame.draw.line(surface, (255, 255, 255), outer.topleft, outer.topright)    # top highlight
    pygame.draw.line(surface, (255, 255, 255), outer.topleft, outer.bottomleft)  # left highlight


def draw_background(screen, background_image):
    """Draw the background image (or a plain color) and darken it a bit."""
    if background_image:
        screen.blit(background_image, (0, 0))
    else:
        screen.fill(FALLBACK_BACKGROUND_COLOR)

    darkener = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    darkener.set_alpha(BACKGROUND_DARKNESS)  # semi-transparent black
    screen.blit(darkener, (0, 0))


def draw_board(screen):
    """Draw the dark board, its grid lines and the glowing border."""
    board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_COLUMNS * BLOCK_SIZE, BOARD_ROWS * BLOCK_SIZE)
    pygame.draw.rect(screen, BOARD_COLOR, board_rect)

    for column in range(BOARD_COLUMNS + 1):
        x = BOARD_LEFT + column * BLOCK_SIZE
        pygame.draw.line(screen, GRID_LINE_COLOR, (x, board_rect.top), (x, board_rect.bottom))
    for row in range(BOARD_ROWS + 1):
        y = BOARD_TOP + row * BLOCK_SIZE
        pygame.draw.line(screen, GRID_LINE_COLOR, (board_rect.left, y), (board_rect.right, y))

    # Three rectangles of different thickness/color make a glowing border.
    for thickness, color in [(6, (40, 40, 80)), (3, (80, 80, 160)), (1, (140, 140, 255))]:
        pygame.draw.rect(screen, color, board_rect.inflate(thickness * 2, thickness * 2), thickness)


def draw_ghost_piece(screen, game):
    """Draw a dim outline showing where the piece will land."""
    landing_row = game.landing_row()
    dim_color = [value // 2 for value in game.piece_color]
    for offset_x, offset_y in game.piece_offsets:
        row = landing_row + offset_y
        if row < 0:
            continue
        pixel_x, pixel_y = board_to_pixels(game.piece_x + offset_x, row)
        outline = pygame.Rect(pixel_x + 1, pixel_y + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2)
        pygame.draw.rect(screen, dim_color, outline, 1)


def draw_blocks_with_bloom(screen, game, glow_layer):
    """
    Draw all blocks, then add a glow on top ("bloom").

    How the glow works:
      1. Draw the blocks onto a separate black layer.
      2. Shrink that layer a lot, then stretch it back to full size.
         Shrinking throws away detail, so stretching back looks blurry.
      3. ADD the blurry layer on top of the screen. Adding light = glow!
    """
    # Every square to draw: the locked ones plus the falling piece.
    all_blocks = [(column, row, color) for (column, row), color in game.locked_blocks.items()]
    for offset_x, offset_y in game.piece_offsets:
        all_blocks.append((game.piece_x + offset_x, game.piece_y + offset_y, game.piece_color))

    glow_layer.fill((0, 0, 0))
    for column, row, color in all_blocks:
        if row < 0:
            continue  # this square is still above the top of the board
        pixel_x, pixel_y = board_to_pixels(column, row)
        draw_block(screen, color, pixel_x, pixel_y)
        draw_block(glow_layer, color, pixel_x, pixel_y)

    for blur_amount in BLOOM_BLUR_LEVELS:
        small_size = (WINDOW_WIDTH // blur_amount, WINDOW_HEIGHT // blur_amount)
        small = pygame.transform.smoothscale(glow_layer, small_size)
        blurry = pygame.transform.smoothscale(small, (WINDOW_WIDTH, WINDOW_HEIGHT))
        screen.blit(blurry, (0, 0), special_flags=BLEND_RGB_ADD)


def draw_interface(screen, game, small_font, big_font):
    """Draw text and the 'next piece' preview. Drawn AFTER the bloom so text stays sharp."""
    screen.blit(big_font.render("TETRIS", True, TITLE_COLOR), (WINDOW_WIDTH // 2 - 70, 14))

    side_x = BOARD_LEFT + BOARD_COLUMNS * BLOCK_SIZE + 25   # the panel right of the board
    stats = [f"SCORE {game.score}", f"LINES {game.lines_cleared}", f"LVL   {game.level}"]
    for index, text in enumerate(stats):
        screen.blit(small_font.render(text, True, TEXT_COLOR), (side_x, BOARD_TOP + 130 + index * 30))

    screen.blit(small_font.render("NEXT", True, TEXT_COLOR), (side_x, BOARD_TOP + 20))
    next_offsets, next_color = game.next_piece
    for offset_x, offset_y in next_offsets:
        draw_block(screen, next_color,
                   side_x + 30 + offset_x * BLOCK_SIZE,
                   BOARD_TOP + 70 + offset_y * BLOCK_SIZE)

    if game.is_game_over:
        message = big_font.render("GAME OVER - R to restart", True, GAME_OVER_COLOR)
        screen.blit(message, (WINDOW_WIDTH // 2 - message.get_width() // 2, WINDOW_HEIGHT // 2))


def draw_everything(screen, game, background_image, glow_layer, small_font, big_font):
    """Draw one complete frame, back to front."""
    draw_background(screen, background_image)
    draw_board(screen)
    draw_ghost_piece(screen, game)
    draw_blocks_with_bloom(screen, game, glow_layer)
    draw_interface(screen, game, small_font, big_font)


# =============================================================================
# 5. MAIN LOOP
# =============================================================================

# Which arrow keys move the piece, and by how much: key -> (change_x, change_y)
MOVE_KEYS = {K_LEFT: (-1, 0), K_RIGHT: (1, 0)}


def handle_key_press(game, key, is_first_press):
    """
    React to one key press.

    is_first_press is False when the key is just being held down (auto-repeat).
    We only want auto-repeat for moving, not for rotate or hard drop.
    """
    if game.is_game_over:
        return

    if key in MOVE_KEYS:
        change_x, change_y = MOVE_KEYS[key]
        game.try_move(change_x, change_y)
    elif key == K_DOWN:
        game.step_down()
    elif key == K_UP and is_first_press:
        game.rotate()
    elif key == K_SPACE and is_first_press:
        game.hard_drop()


def load_background():
    """Load the background image. Returns None if the file isn't there."""
    try:
        image = pygame.image.load(BACKGROUND_IMAGE).convert()
        return pygame.transform.scale(image, (WINDOW_WIDTH, WINDOW_HEIGHT))
    except (pygame.error, FileNotFoundError):
        return None


def main():
    pygame.init()
    pygame.key.set_repeat(150, 50)   # holding a key repeats it: first after 150ms, then every 50ms
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Tetris")

    background_image = load_background()
    small_font = pygame.font.SysFont("Consolas", 22)
    big_font = pygame.font.SysFont("Consolas", 40, bold=True)
    glow_layer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))   # reused every frame for the bloom

    clock = pygame.time.Clock()
    game = TetrisGame()
    ms_since_last_fall = 0
    keys_being_held = set()

    while True:
        # --- Time: wait for the next frame (max 60 per second) ---
        ms_since_last_fall += clock.tick(60)

        # --- Input: check everything the player did since last frame ---
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                pygame.quit()
                sys.exit()
            elif event.type == KEYUP:
                keys_being_held.discard(event.key)
            elif event.type == KEYDOWN:
                is_first_press = event.key not in keys_being_held
                keys_being_held.add(event.key)
                if event.key == K_r:
                    game = TetrisGame()   # restart: just make a brand-new game
                else:
                    handle_key_press(game, event.key, is_first_press)

        # --- Update: gravity pulls the piece down every so often ---
        if not game.is_game_over and ms_since_last_fall > game.fall_delay_ms:
            ms_since_last_fall = 0
            game.step_down()

        # --- Draw: show the new frame ---
        draw_everything(screen, game, background_image, glow_layer, small_font, big_font)
        pygame.display.flip()


# Idea list for students (pick one!):
#   - Change PIECES colors or invent a new 5-square piece
#   - Add a "hold" piece (press C to swap it with the next piece)
#   - Add sound effects when you clear a line (pygame.mixer)
#   - Make a pause key (P)
#   - Show a high score that is saved to a file
#   - Change draw_block() to make your own block style

if __name__ == "__main__":
    main()