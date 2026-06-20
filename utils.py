"""Pure poker logic utilities: card parsing, equity simulation, advice.

Nothing in here prints or renders -- it's all computation so it can be
reused by the CLI, the visual board, or tests.
"""

from treys import Card, Evaluator, Deck

# One shared evaluator; constructing it is cheap but there's no reason to
# rebuild it on every call.
evaluator = Evaluator()


def parse_card(s):
    """Turn a string like "Ah", "Td", "2c" into a treys card int."""
    return Card.new(s)


def card_to_str(card_int):
    """treys card int -> 'Ah' style string the renderers understand."""
    return Card.int_to_str(card_int)


def deal_hand(num_opponents):
    """Shuffle and deal a hero hand, opponent hands, and a full board.

    Returns (hero, opponents, full_board) as lists of treys card ints.
    """
    deck = Deck()
    hero = deck.draw(2)
    opponents = [deck.draw(2) for _ in range(num_opponents)]
    full_board = deck.draw(5)
    return hero, opponents, full_board


def showdown_winner(hero, opponents, board_ints):
    """Decide a showdown.

    Returns ('hero'|'opponents'|'tie', best_opponent_seat_index).
    """
    hero_score = evaluator.evaluate(board_ints, hero)
    opp_scores = [evaluator.evaluate(board_ints, oh) for oh in opponents]
    best_opp = min(opp_scores)
    seat = opp_scores.index(best_opp)
    if hero_score < best_opp:
        return "hero", seat
    if hero_score > best_opp:
        return "opponents", seat
    return "tie", seat


def hand_class(cards, board_ints):
    """Human-readable hand class, e.g. 'Three of a Kind'."""
    rank = evaluator.evaluate(board_ints, cards)
    return evaluator.class_to_string(evaluator.get_rank_class(rank))


def equity(hole, board, num_opponents, iterations=1000):
    """Monte-Carlo win/tie rate for a hand.

    hole: list of 2 card strings, e.g. ["Ah", "Kh"]
    board: list of 0-5 card strings already on the table
    num_opponents: how many other players are in the hand

    Returns (win_rate, tie_rate) as fractions of `iterations`.
    """
    my_hole = [parse_card(c) for c in hole]
    known_board = [parse_card(c) for c in board]

    wins = 0
    ties = 0

    for _ in range(iterations):
        deck = Deck()
        # remove known cards from the deck
        for c in my_hole + known_board:
            deck.cards.remove(c)

        # deal opponents (draw(2) returns a list of 2 cards)
        opp_holes = [deck.draw(2) for _ in range(num_opponents)]

        # complete the board to 5 cards
        needed = 5 - len(known_board)
        sim_board = known_board + (deck.draw(needed) if needed else [])
        # draw(1) returns a single int rather than a list; normalize
        if not isinstance(sim_board, list):
            sim_board = [sim_board]

        my_score = evaluator.evaluate(sim_board, my_hole)
        opp_scores = [evaluator.evaluate(sim_board, oh) for oh in opp_holes]

        best_opp = min(opp_scores)  # lower is better in treys
        if my_score < best_opp:
            wins += 1
        elif my_score == best_opp:
            ties += 1

    return wins / iterations, ties / iterations


def recommendation(eq, num_opponents):
    """Map an equity figure to a plain-language betting recommendation.

    Returns (text, fair_share) where fair_share is the break-even equity
    against this many opponents.
    """
    fair_share = 1 / (num_opponents + 1)
    if eq > fair_share * 1.5:
        rec = "Strong. Bet or raise for value."
    elif eq > fair_share:
        rec = "Ahead of average. Bet or call."
    elif eq > fair_share * 0.7:
        rec = "Marginal. Call if cheap, fold to pressure."
    else:
        rec = "Behind. Fold unless you have a cheap draw."
    return rec, fair_share


def advise(hole, board, num_opponents, iterations=1000):
    """Convenience wrapper: compute equity and a recommendation in one call.

    Returns a dict so callers can render it however they like.
    """
    win, tie = equity(hole, board, num_opponents, iterations)
    eq = win + tie / 2  # split ties as half a win
    rec, fair_share = recommendation(eq, num_opponents)
    return {
        "hole": hole,
        "board": board,
        "num_opponents": num_opponents,
        "win": win,
        "tie": tie,
        "equity": eq,
        "recommendation": rec,
        "fair_share": fair_share,
    }
