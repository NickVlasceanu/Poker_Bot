"""Interactive Texas Hold'em in the terminal, with a built-in coach.

You play against equity-driven opponents and make real fold/check/call/bet/
raise decisions. Before every decision the coach shows your pot odds, equity,
EV, outs and implied odds, then a recommended action -- so you learn *why*.

Run:  python main.py
      python main.py --opponents 3 --stack 1500
"""

import argparse
import os
import sys

import board
import coach
import opponent
from engine import PokerGame
from utils import advise, card_to_str


def _init_terminal():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if os.name == "nt":
        os.system("")


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render(game, reveal=False):
    out = []
    line = "═" * 56
    out.append(f"{board.GREEN}╔{line}╗{board.RESET}")
    title = f" HOLD'EM — {game.stage.upper()} ".center(56)
    out.append(f"{board.GREEN}║{board.RESET}{board.BOLD}{title}{board.RESET}"
               f"{board.GREEN}║{board.RESET}")
    out.append(f"{board.GREEN}╚{line}╝{board.RESET}")
    out.append(f"{board.YELLOW}Pot: {game.pot()}   "
               f"Current bet: {game.current_bet}{board.RESET}")
    out.append("")

    # opponents
    for i, p in enumerate(game.players):
        if p.is_hero:
            continue
        flags = []
        if p.folded:
            flags.append(f"{board.DIM}folded{board.RESET}")
        if p.all_in:
            flags.append(f"{board.RED}all-in{board.RESET}")
        if i == game.to_act:
            flags.append(f"{board.YELLOW}◄ to act{board.RESET}")
        tag = ("  " + "  ".join(flags)) if flags else ""
        cards = ""
        if reveal and not p.folded:
            cards = "  " + " ".join(card_to_str(c) for c in p.hole)
        out.append(f"{board.BOLD}{p.name}{board.RESET}  "
                   f"stack {p.stack}  bet {p.street_contrib}{tag}{cards}")

    # board cards
    out.append("")
    out.append(f"{board.YELLOW}Community:{board.RESET}")
    if game.board:
        out.append(board.render_row([card_to_str(c) for c in game.board], pad_to=5))
    else:
        out.append(board.render_row([], pad_to=5))

    # hero
    hero = game.players[0]
    out.append("")
    htag = f"  {board.YELLOW}◄ your turn{board.RESET}" if game.to_act == 0 else ""
    out.append(f"{board.BOLD}{hero.name}{board.RESET}  stack {hero.stack}  "
               f"bet {hero.street_contrib}{htag}")
    out.append(board.render_row([card_to_str(c) for c in hero.hole]))
    return "\n".join(out)


# --------------------------------------------------------------------------
# Coaching for the hero's live decision
# --------------------------------------------------------------------------
def show_coach(game):
    hero = game.players[0]
    opponents_in = max(1, len(game.in_hand_indices()) - 1)
    hole = [card_to_str(c) for c in hero.hole]
    cards = [card_to_str(c) for c in game.board]
    eq = advise(hole, cards, opponents_in, iterations=800)
    to_call = game.to_call(0)
    pot = game.pot()
    behind = _behind(game)
    print()
    print(coach.coach(eq, to_call, pot, cards, hole, opponents_in, behind=behind))
    print()


def _behind(game):
    """Chips you could still win from opponents on later streets."""
    hero = game.players[0]
    opp_stacks = [p.stack for i, p in enumerate(game.players)
                  if i != 0 and p.in_hand and not p.all_in]
    if not opp_stacks:
        return 0
    return min(hero.stack, max(opp_stacks))


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
def prompt_hero(game):
    la = game.legal_actions(0)
    call_amt = la["call"]
    opts = ["[f]old"]
    if la["check"]:
        opts.append("[k]check")
    if la["can_call"]:
        opts.append(f"[c]call {call_amt}")
    if la["can_raise"]:
        verb = "bet" if la["bet"] else "raise"
        opts.append(f"[r]{verb} (min {la['min_to']}, max {la['max_to']})")
    print("  " + "   ".join(opts))

    while True:
        try:
            choice = input("  Your action: ").strip().lower()
        except EOFError:
            return "fold", None
        if choice in ("f", "fold"):
            return "fold", None
        if choice in ("k", "check") and la["check"]:
            return "check", None
        if choice in ("c", "call") and la["can_call"]:
            return "call", None
        if choice and choice[0] == "r" and la["can_raise"]:
            rest = choice[1:].strip()
            amount = int(rest) if rest.isdigit() else la["min_to"]
            return ("bet" if la["bet"] else "raise"), amount
        print("  Invalid — try again.")


# --------------------------------------------------------------------------
# Game loop
# --------------------------------------------------------------------------
def play(num_opponents, stack, sb, bb):
    game = PokerGame(num_opponents=num_opponents, starting_stack=stack,
                     sb=sb, bb=bb)
    hand_no = 0
    while sum(1 for p in game.players if p.stack > 0) >= 2 and game.players[0].stack > 0:
        hand_no += 1
        game.start_hand()
        while not game.hand_over():
            idx = game.to_act
            if idx is None:
                break
            if idx == 0:
                _clear()
                print(render(game))
                show_coach(game)
                action, amount = prompt_hero(game)
                game.act(action, amount)
            else:
                action, amount = opponent.choose(game, idx)
                game.act(action, amount)

        _clear()
        print(render(game, reveal=True))
        print()
        print(f"{board.BOLD}--- Showdown ---{board.RESET}")
        for r in game.results:
            print(f"  {board.GREEN}{r}{board.RESET}")
        if not game.players[0].folded and len(game.in_hand_indices()) > 1:
            print(f"  Your hand: {game.hand_class(0)}")
        print()
        if game.players[0].stack <= 0:
            print(f"{board.RED}You're out of chips. Game over.{board.RESET}")
            break
        try:
            cont = input("  Press Enter for the next hand (or 'q' to quit): ").strip().lower()
        except EOFError:
            break
        if cont == "q":
            break
        game.rotate_button()

    print(f"\nFinal stack: {game.players[0].stack}")


def main():
    parser = argparse.ArgumentParser(description="Interactive Hold'em with a coach")
    parser.add_argument("--opponents", type=int, default=2)
    parser.add_argument("--stack", type=int, default=1000)
    parser.add_argument("--sb", type=int, default=10)
    parser.add_argument("--bb", type=int, default=20)
    args = parser.parse_args()

    _init_terminal()
    play(args.opponents, args.stack, args.sb, args.bb)


if __name__ == "__main__":
    main()
