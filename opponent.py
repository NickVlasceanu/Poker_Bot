"""Equity-driven opponent AI for the full game.

Given the live game state, an opponent decides fold / check / call / bet / raise
using the same numbers the coach teaches the hero: its own equity, its fair
share of the pot, the pot odds it's being offered, and how many outs it has.
A disciplined slice of weak hands bluff (and strong draws semi-bluff) so the
bet sizes carry real information.
"""

import random as _random

import coach
from utils import advise, card_to_str

# Bet/raise sizing as a fraction of the pot.
VALUE_SIZE = 0.70
THIN_SIZE = 0.45
BLUFF_SIZE = 0.70
RAISE_SIZE = 1.0     # raises add about one pot on top of the call

# Frequencies (the judgement knobs). ~1 bluff per 2 value bets keeps a
# pot-ish bet roughly balanced; semi-bluffs add a few more aggressive lines.
BLUFF_FREQ = 0.28
SEMI_BLUFF_FREQ = 0.45
VALUE_RAISE_FREQ = 0.6


def choose(game, idx, iterations=200, rng=_random):
    """Return (action, amount) -- a legal action for player `idx` to act.

    `amount` is a 'raise to' total (only for bet/raise), else None.
    """
    p = game.players[idx]
    hole = [card_to_str(c) for c in p.hole]
    board = [card_to_str(c) for c in game.board]
    opponents_in = max(1, len(game.in_hand_indices()) - 1)

    eq = advise(hole, board, opponents_in, iterations)["equity"]
    fair = 1.0 / (opponents_in + 1)
    outs, _ = coach.count_outs(hole, board)
    strong_draw = outs >= 8

    la = game.legal_actions(idx)
    pot = game.pot()
    to_call = la["call"]

    # ---- no bet to us: check or bet ------------------------------------
    if to_call == 0:
        if eq >= fair * 1.5:
            return _aggress(game, idx, la, pot, VALUE_SIZE, rng)
        if eq >= fair and rng.random() < 0.5:
            return _aggress(game, idx, la, pot, THIN_SIZE, rng)
        if board and strong_draw and rng.random() < SEMI_BLUFF_FREQ:
            return _aggress(game, idx, la, pot, BLUFF_SIZE, rng)
        if board and eq < fair * 0.6 and rng.random() < BLUFF_FREQ:
            return _aggress(game, idx, la, pot, BLUFF_SIZE, rng)
        return ("check", None)

    # ---- facing a bet: fold / call / raise -----------------------------
    required = to_call / (pot + to_call)

    # premium: raise for value
    if eq >= max(required * 1.7, 0.62) and rng.random() < VALUE_RAISE_FREQ:
        return _aggress(game, idx, la, pot, RAISE_SIZE, rng)

    # priced in: call
    if eq >= required:
        return ("call", None)

    # strong draw: semi-bluff raise sometimes, else call if close (implied odds)
    if strong_draw:
        if rng.random() < SEMI_BLUFF_FREQ:
            return _aggress(game, idx, la, pot, BLUFF_SIZE, rng)
        if eq >= required * 0.7:            # close enough with chips behind
            return ("call", None)

    # otherwise it's a fold
    return ("fold", None)


def _aggress(game, idx, la, pot, frac, rng):
    """Build a legal bet/raise of about `frac` of the pot, or fall back."""
    if not la["can_raise"]:
        # can't raise (e.g. too short) -- call if facing a bet, else check
        return ("call", None) if la["can_call"] else ("check", None)

    target = game.current_bet + round(pot * frac)
    if game.current_bet == 0:
        target = round(pot * frac)
        action = "bet"
    else:
        action = "raise"
    target = max(la["min_to"], min(target, la["max_to"]))
    return (action, target)
