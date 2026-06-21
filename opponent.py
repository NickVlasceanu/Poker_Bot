"""Equity-driven opponents.

Each opponent looks at its OWN hole cards and acts on the same logic the coach
applies to the hero: bet/raise when equity beats its fair share, check or bluff
when weak. This replaces the old random bet, so a bet size now actually means
something -- a big bet genuinely represents a strong range, with a disciplined
share of bluffs mixed in.
"""

import random as _random

from utils import advise

# Bet sizes as a fraction of the current pot.
VALUE_SIZE = 0.75   # strong hands bet big
THIN_SIZE = 0.50    # decent hands bet smaller
BLUFF_SIZE = 0.75   # bluffs copy the value size so they're indistinguishable

# How often a weak hand turns into a bluff instead of giving up.
# Anchored to balance: against a ~pot-sized bet a caller's break-even equity --
# and therefore the share of bluffs that keeps them indifferent -- is about 1/3,
# i.e. roughly one bluff for every two value bets. We approximate that target
# mix with this fixed rate; it's the one knob tuned by judgment.
BLUFF_FREQ = 0.30


def decide(hole, board, num_opponents, pot, iterations=300, rng=_random):
    """One opponent's action for the current street.

    Returns a dict: action 'bet'|'check', kind 'value'|'thin'|'bluff'|'give-up',
    size (chips), equity.
    """
    eq = advise(hole, board, num_opponents, iterations)["equity"]
    fair = 1 / (num_opponents + 1)

    if eq >= fair * 1.4:                       # clear favorite -> value bet
        return _bet("value", round(pot * VALUE_SIZE), eq)
    if eq >= fair:                             # decent -> bet thin sometimes
        if rng.random() < 0.5:
            return _bet("thin", round(pot * THIN_SIZE), eq)
        return _check("thin", eq)
    if board and rng.random() < BLUFF_FREQ:    # weak -> occasional bluff
        return _bet("bluff", round(pot * BLUFF_SIZE), eq)
    return _check("give-up", eq)               # weak -> give up


def table_action(opp_holes, board, num_opponents, pot, iterations=300,
                 rng=_random):
    """Resolve a betting round: the strongest bettor is what the hero faces.

    opp_holes: list of [card_str, card_str] for each opponent.
    Returns (aggressor_dict_or_None, all_actions). The aggressor dict carries
    a "seat" index (0-based).
    """
    actions = []
    for seat, hole in enumerate(opp_holes):
        a = decide(hole, board, num_opponents, pot, iterations, rng)
        a["seat"] = seat
        actions.append(a)

    bettors = [a for a in actions if a["action"] == "bet"]
    if not bettors:
        return None, actions
    aggressor = max(bettors, key=lambda a: a["equity"])
    return aggressor, actions


def _bet(kind, size, eq):
    return {"action": "bet", "kind": kind, "size": max(20, size), "equity": eq}


def _check(kind, eq):
    return {"action": "check", "kind": kind, "size": 0, "equity": eq}
