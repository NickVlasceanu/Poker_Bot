"""Visual rendering for the poker game.

Draws actual ASCII playing cards and a table layout so a simulated hand
looks like a game being dealt instead of a wall of printed numbers.
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


def _equity_bar(eq, width=24):
    """A colored progress bar for a 0..1 equity value."""
    filled = int(round(eq * width))
    color = GREEN if eq >= 0.5 else YELLOW if eq >= 0.3 else RED
    bar = "█" * filled + DIM + "░" * (width - filled) + RESET
    return f"{color}{bar}{RESET}"


def render_table(state):
    """Render the full table for one moment of a hand.

    state keys:
      street      -- "Pre-flop" / "Flop" / "Turn" / "River" / "Showdown"
      board       -- list of community card strings dealt so far
      hero        -- list of hero's 2 hole cards
      opponents   -- int, number of opponents
      pot         -- int chip count
      reveal_opps -- optional list of opponent hole-card pairs to show
      equity      -- optional dict from utils.advise()
    """
    out = []
    line = "═" * 52
    out.append(f"{GREEN}╔{line}╗{RESET}")

    title = f" {state['street'].upper()} ".center(52, " ")
    out.append(f"{GREEN}║{RESET}{BOLD}{title}{RESET}{GREEN}║{RESET}")
    out.append(f"{GREEN}╚{line}╝{RESET}")

    # Opponents (face down, or revealed at showdown)
    reveal = state.get("reveal_opps")
    out.append(f"{DIM}Opponents ({state['opponents']}):{RESET}")
    if reveal:
        for i, opp in enumerate(reveal, 1):
            out.append(f"  {DIM}Seat {i}{RESET}")
            out.append(render_row(opp))
    else:
        # one face-down pair per opponent, laid out side by side with a gap
        opp_backs = [render_row(["", ""], hidden=True)
                     for _ in range(state["opponents"])]
        merged = []
        for row in range(5):
            merged.append("    ".join(h.split("\n")[row] for h in opp_backs))
        out.append("\n".join(merged))

    out.append("")
    potline = f"{YELLOW}Pot: {state['pot']} chips{RESET}"
    to_call = state.get("to_call")
    if to_call:
        seat = state.get("bettor_seat")
        who = f"Seat {seat + 1}" if seat is not None else "Opponent"
        potline += f"   {RED}{who} bets {to_call} — {to_call} to call{RESET}"
    out.append(f"{YELLOW}Community board:{RESET}   {potline}")
    out.append(render_row(state["board"], pad_to=5))

    out.append("")
    out.append(f"{BOLD}Your hand:{RESET}")
    out.append(render_row(state["hero"]))

    eq = state.get("equity")
    if eq:
        out.append("")
        out.append(
            f"  Win {GREEN}{eq['win']:.0%}{RESET}  "
            f"Tie {DIM}{eq['tie']:.0%}{RESET}  "
            f"Equity {BOLD}{eq['equity']:.0%}{RESET}"
        )
        out.append(f"  {_equity_bar(eq['equity'])} {eq['equity']:.0%}")
        out.append(f"  {DIM}Fair share vs {state['opponents']} opp: "
                   f"{eq['fair_share']:.0%}{RESET}")
        out.append(f"  ➜ {BOLD}{eq['recommendation']}{RESET}")

    return "\n".join(out)
