"""ASCII card rendering and ANSI colors for the terminal game.

Provides the playing-card art and color constants used by the terminal UI
(main.py). The interactive table layout itself lives in main.py.
"""

# --- ANSI colors -----------------------------------------------------------
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"

SUITS = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}  # ♥ ♦ ♠ ♣
RED_SUITS = {"h", "d"}

CARD_W = 7  # printed width of one rendered card


def _rank(s):
    """Display rank: 'T' becomes '10', everything else stays as-is."""
    return "10" if s[0].upper() == "T" else s[0].upper()


def render_card(card_str):
    """Return the 5 lines of a face-up card like 'Ah'."""
    rank = _rank(card_str)
    suit_letter = card_str[1].lower()
    suit = SUITS[suit_letter]
    color = RED if suit_letter in RED_SUITS else ""

    # left-justified top rank, right-justified bottom rank (width 2)
    top = rank.ljust(2)
    bot = rank.rjust(2)
    body = f"{color}" if color else ""
    end = RESET if color else ""

    return [
        "╭─────╮",          # ╭─────╮
        f"│{body}{top}{end}   │",                     # │A    │
        f"│  {body}{suit}{end}  │",                   # │  ♥  │
        f"│   {body}{bot}{end}│",                     # │    A│
        "╰─────╯",          # ╰─────╯
    ]


def render_back():
    """Return the 5 lines of a face-down card."""
    return [
        "╭─────╮",
        f"│{DIM}▒▒▒▒▒{RESET}│",
        f"│{DIM}▒▒▒▒▒{RESET}│",
        f"│{DIM}▒▒▒▒▒{RESET}│",
        "╰─────╯",
    ]


def _empty_slot():
    """A placeholder for a board card not yet dealt."""
    return [
        "┌┄┄┄┄┄┐",
        "┆     ┆",
        "┆     ┆",
        "┆     ┆",
        "└┄┄┄┄┄┘",
    ]


def render_row(cards, hidden=False, pad_to=None):
    """Render a sequence of cards side by side as a multi-line string.

    cards: list of card strings.
    hidden: if True, draw card backs instead of faces.
    pad_to: if set, append empty slots up to this many cards.
    """
    rendered = []
    for c in cards:
        rendered.append(render_back() if hidden else render_card(c))
    if pad_to:
        for _ in range(pad_to - len(cards)):
            rendered.append(_empty_slot())

    if not rendered:
        return ""

    lines = []
    for row in range(5):
        lines.append(" ".join(block[row] for block in rendered))
    return "\n".join(lines)
