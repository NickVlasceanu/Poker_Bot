"""Poker equity bot -- visual game simulation.

Deals a real hand with treys and walks through it street by street, drawing
the table and updating the hero's equity at each stage, ending in a showdown.

Run:  python main.py            (simulate a full hand)
      python main.py --hands 3  (simulate several hands)
"""

import argparse
import os
import sys
import time

import board
import coach
import opponent
from utils import advise, deal_hand, showdown_winner, hand_class, card_to_str


def _init_terminal():
    """Make the Windows console show unicode cards and ANSI colors."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if os.name == "nt":
        # Enables ANSI escape processing on Windows 10+ consoles.
        os.system("")

STREETS = [
    ("Pre-flop", 0),
    ("Flop", 3),
    ("Turn", 4),
    ("River", 5),
]


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def play_hand(num_opponents=2, pause=1.6):
    hero, opponents, full_board = deal_hand(num_opponents)
    hero_str = [card_to_str(c) for c in hero]
    board_str = [card_to_str(c) for c in full_board]

    pot = 20 * (num_opponents + 1)  # everyone antes in
    for street, n in STREETS:
        shown_board = board_str[:n]

        # Opponents act on their own cards (except pre-flop = just the antes).
        to_call = 0
        bettor_seat = None
        if street != "Pre-flop":
            opp_holes = [[card_to_str(c) for c in opp] for opp in opponents]
            aggressor, _ = opponent.table_action(
                opp_holes, shown_board, num_opponents, pot)
            if aggressor:
                to_call = aggressor["size"]
                bettor_seat = aggressor["seat"]
                pot += to_call  # their chips go in before we decide

        eq = advise(hero_str, shown_board, num_opponents)

        _clear()
        print(board.render_table({
            "street": street,
            "board": shown_board,
            "hero": hero_str,
            "opponents": num_opponents,
            "pot": pot,
            "to_call": to_call,
            "bettor_seat": bettor_seat,
            "equity": eq,
        }))
        print()
        print(coach.coach(eq, to_call, pot, shown_board, hero_str, num_opponents))

        if to_call:
            pot += to_call  # we call to see the next street
        time.sleep(pause)

    # --- Showdown ---------------------------------------------------------
    result, seat = showdown_winner(hero, opponents, full_board)
    reveal = [[card_to_str(c) for c in opp] for opp in opponents]

    _clear()
    print(board.render_table({
        "street": "Showdown",
        "board": board_str,
        "hero": hero_str,
        "opponents": num_opponents,
        "pot": pot,
        "reveal_opps": reveal,
    }))

    hero_class = hand_class(hero, full_board)
    print()
    print(f"  {board.BOLD}Your best hand: {hero_class}{board.RESET}")
    if result == "hero":
        print(f"  {board.GREEN}{board.BOLD}*** YOU WIN {pot} chips! ***{board.RESET}")
    elif result == "tie":
        print(f"  {board.YELLOW}*** SPLIT POT with seat {seat + 1} ***{board.RESET}")
    else:
        print(f"  {board.RED}Seat {seat + 1} wins. Better luck next hand.{board.RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Visual poker equity simulation")
    parser.add_argument("--hands", type=int, default=1, help="number of hands to play")
    parser.add_argument("--opponents", type=int, default=2, help="opponents at the table")
    parser.add_argument("--pause", type=float, default=1.6, help="seconds between streets")
    args = parser.parse_args()

    _init_terminal()
    for i in range(args.hands):
        play_hand(num_opponents=args.opponents, pause=args.pause)
        if i < args.hands - 1:
            input("  Press Enter to deal the next hand...")


if __name__ == "__main__":
    main()
