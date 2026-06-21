"""Educational poker coach.

Takes a moment in a hand (your equity, the pot, the bet you're facing) and
explains the *reasoning* behind a fold/call/raise: pot odds, expected value,
outs, and the rule of 4 and 2. Everything returns plain text so it reads the
same in the terminal or in the GUI's coach panel.

The goal is intuition: every number is shown with the sentence that tells you
what it means, so you can reproduce the thinking at a real table.
"""

RANK_VAL = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}
SUIT_SYMBOL = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}


# --------------------------------------------------------------------------
# Pot odds & expected value
# --------------------------------------------------------------------------
def pot_odds(to_call, pot):
    """Return (required_equity, ratio) for calling `to_call` into `pot`.

    `pot` already includes the opponent's bet. If you call, the final pot is
    pot + to_call, of which you contributed to_call -- so you need to win at
    least to_call / (pot + to_call) of the time just to break even.
    """
    if to_call <= 0:
        return 0.0, float("inf")
    required = to_call / (pot + to_call)
    ratio = pot / to_call  # pot : call, e.g. 3.0 means "3 to 1"
    return required, ratio


def call_ev(equity, to_call, pot):
    """Chips you make (or lose) on average by calling.

    Win  -> you collect the `pot` that's already out there  (+pot)
    Lose -> you forfeit your call                            (-to_call)
    EV = equity * pot - (1 - equity) * to_call
    """
    return equity * pot - (1 - equity) * to_call


# --------------------------------------------------------------------------
# Outs & the rule of 4 and 2
# --------------------------------------------------------------------------
def count_outs(hole, board):
    """Detect the common draws and count outs.

    Only meaningful with cards still to come (flop or turn). Returns
    (total_outs, [(name, outs), ...]). Approximate by design -- it covers
    flush and straight draws, which is what the rule of 4 and 2 is built for.
    """
    if not (3 <= len(board) <= 4):
        return 0, []

    cards = hole + board
    draws = []

    # --- flush draw: four of one suit, one more to come -------------------
    flush_outs = 0
    suits = [c[1].lower() for c in cards]
    for s in "hdcs":
        if suits.count(s) == 4:
            flush_outs = 9  # 13 of a suit minus the 4 you can see
            draws.append((f"Flush draw ({SUIT_SYMBOL[s]})", 9))

    # --- straight draw ---------------------------------------------------
    present = set()
    for c in cards:
        v = RANK_VAL[c[0].upper()]
        present.add(v)
        if v == 14:
            present.add(1)  # ace can also play low (A-2-3-4-5)

    completing = set()
    for start in range(1, 11):                  # windows A-5 ... T-A
        window = set(range(start, start + 5))
        if len(window & present) == 4:          # one card short of a straight
            completing |= (window - present)    # the rank that completes it

    if completing:
        straight_outs = min(len(completing) * 4, 8)
        kind = ("Open-ended straight draw" if len(completing) >= 2
                else "Gutshot straight draw")
        draws.append((kind, straight_outs))
    else:
        straight_outs = 0

    return flush_outs + straight_outs, draws


def rule_of_4_and_2(outs, cards_to_come):
    """Quick equity estimate from outs -- the rule every player memorizes.

    Flop (2 cards to come): outs x 4.   Turn (1 card to come): outs x 2.
    Returns an approximate percentage (0-100).
    """
    if outs <= 0 or cards_to_come <= 0:
        return 0
    return outs * (4 if cards_to_come >= 2 else 2)


# --------------------------------------------------------------------------
# The full explanation
# --------------------------------------------------------------------------
def coach(eq, to_call, pot, board, hole, num_opponents):
    """Build the multi-line teaching text for one decision point.

    eq: dict from utils.advise (win/tie/equity/fair_share).
    to_call: chips you must put in to continue (0 = checked to you).
    pot: chips in the middle, including any bet you're facing.
    """
    e = eq["equity"]
    fair = eq["fair_share"]
    cards_to_come = 5 - len(board)
    lines = []

    def section(title):
        lines.append("")
        lines.append(title)

    # ---- pot odds -------------------------------------------------------
    if to_call > 0:
        required, ratio = pot_odds(to_call, pot)
        section("POT ODDS — the price of a call")
        lines.append(f"  Pot is {pot}, it's {to_call} to call  ->  you're getting "
                     f"{ratio:.1f} : 1.")
        lines.append(f"  Break-even equity = {to_call} / ({pot} + {to_call}) = "
                     f"{required:.0%}.")
        lines.append(f"  That means a call only has to win {required:.0%} of the "
                     "time to break even.")

        section("YOUR EQUITY vs THE PRICE")
        gap = e - required
        lines.append(f"  Simulation: {e:.0%} equity   vs   {required:.0%} needed.")
        if gap >= 0:
            lines.append(f"  You're {gap:+.0%} above the line — the call wins more "
                         "often than it has to.")
        else:
            lines.append(f"  You're {gap:+.0%} short of the line — raw odds say "
                         "this call loses money.")

        section("EXPECTED VALUE")
        ev = call_ev(e, to_call, pot)
        sign = "makes" if ev >= 0 else "loses"
        lines.append(f"  EV(call) ≈ {ev:+.0f} chips. You risk {to_call} to win "
                     f"{pot}; at {e:.0%} that {sign} money over time.")

        section("WHAT THE BET REPRESENTS")
        pot_before = pot - to_call
        frac = to_call / pot_before if pot_before > 0 else 1.0
        lines.append(f"  That's a {frac:.0%}-pot bet. A balanced bettor is "
                     f"value-heavy here: only about {required:.0%} of these bets "
                     "are bluffs, the rest are real hands.")
        lines.append(f"  Note {required:.0%} is also your break-even price — not a "
                     "coincidence. A balanced opponent bluffs JUST enough to make "
                     "your call a coin flip.")
        lines.append("  So the read decides it: call if you think THIS player "
                     "bluffs more than that, fold if less.")
    else:
        section("NO BET — it's checked to you")
        lines.append("  Nothing to call, so there are no pot odds to beat. The "
                     "question is only whether *you* should bet.")

    # ---- outs / rule of 4 and 2 ----------------------------------------
    total_outs, draws = count_outs(hole, board)
    if cards_to_come == 0:
        section("OUTS")
        lines.append("  River — no more cards. Your hand is final; equity is just "
                     "how often it's already best.")
    elif total_outs > 0:
        section("OUTS & THE RULE OF 4 AND 2")
        for name, outs in draws:
            lines.append(f"  {name}: {outs} outs.")
        est = rule_of_4_and_2(total_outs, cards_to_come)
        mult = 4 if cards_to_come >= 2 else 2
        lines.append(f"  {total_outs} outs x {mult} ≈ {est}% to improve by the "
                     "river.")
        lines.append(f"  (The full sim says {e:.0%}; the gap is made hands and "
                     "overcards the shortcut ignores.)")

    # ---- the decision ---------------------------------------------------
    section("DECISION  ->  " + _verdict_headline(e, fair, to_call, pot, total_outs,
                                                  cards_to_come))
    for reason in _verdict_reasons(e, fair, to_call, pot, total_outs,
                                    cards_to_come):
        lines.append("  " + reason)

    return "\n".join(lines).strip("\n")


def _verdict_headline(e, fair, to_call, pot, outs, cards_to_come):
    required = pot_odds(to_call, pot)[0] if to_call > 0 else 0
    strong_draw = outs >= 8 and cards_to_come >= 1

    if to_call == 0:
        if e > fair * 1.4:
            return "BET FOR VALUE"
        if strong_draw:
            return "BET (SEMI-BLUFF)"
        return "CHECK"

    margin = e - required
    if margin <= -0.06 and not strong_draw:
        return "FOLD"
    if e > 0.58 and margin > 0.12:
        return "RAISE FOR VALUE"
    if strong_draw and margin > -0.02:
        return "RAISE (SEMI-BLUFF) or CALL"
    if margin <= 0 and strong_draw:
        return "CALL (DRAWING)"
    return "CALL"


def _verdict_reasons(e, fair, to_call, pot, outs, cards_to_come):
    required = pot_odds(to_call, pot)[0] if to_call > 0 else 0
    strong_draw = outs >= 8 and cards_to_come >= 1
    reasons = []

    if to_call == 0:
        if e > fair * 1.4:
            reasons.append(f"Why: {e:.0%} equity is well above your {fair:.0%} "
                           "fair share vs the field — you're the favorite, so bet "
                           "to grow the pot while ahead.")
            reasons.append("Checking here would let opponents see free cards and "
                           "catch up for nothing.")
        elif strong_draw:
            reasons.append(f"Why: {outs} outs is a lot of equity that's still "
                           "behind right now. Betting can win the pot immediately "
                           "AND improve when called — that's a semi-bluff.")
        else:
            reasons.append(f"Why: {e:.0%} isn't enough to bet for value and you "
                           "have no real draw, so take the free card and reassess.")
        return reasons

    margin = e - required
    if margin <= -0.06 and not strong_draw:
        reasons.append(f"Why: you need {required:.0%} to call but only have "
                       f"{e:.0%} — that's a losing price with no draw to save it. "
                       "Paying off here bleeds chips over time.")
    elif e > 0.58 and margin > 0.12:
        reasons.append(f"Why: {e:.0%} equity crushes the {required:.0%} price. "
                       "Just calling lets opponents off cheap — raise to charge "
                       "draws and build the pot while you're a big favorite.")
    elif strong_draw and margin > -0.02:
        reasons.append(f"Why: with {outs} outs you're rarely far behind, and a "
                       "raise adds fold equity — opponents may fold, and you still "
                       "improve often when they don't.")
    elif margin <= 0 and strong_draw:
        reasons.append(f"Why: pure odds are a hair short ({e:.0%} vs "
                       f"{required:.0%}), but a {outs}-out draw has implied odds — "
                       "the chips you'll win when you hit make the call worthwhile.")
    else:
        reasons.append(f"Why: {e:.0%} clears the {required:.0%} you need, so the "
                       "call is +EV. Not strong enough to raise for value, but "
                       "folding would surrender a profitable spot.")

    reasons.append(f"Rule of thumb: call when equity ({e:.0%}) > pot-odds price "
                   f"({required:.0%}); raise when you're a clear favorite or have "
                   "a big draw with fold equity.")
    return reasons
