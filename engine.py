"""Texas Hold'em game engine -- pure rules, no I/O.

Drives a single hand through blinds, four betting rounds, all-ins, side pots
and showdown. The engine never asks for input: a driver (terminal or GUI)
inspects `to_act`, asks that player for an action, and calls `act(...)`. The
engine then advances to the next actor, the next street, or showdown on its own.

Chips are integers. All bet/raise amounts in the public API are "to" totals --
the target size of a player's contribution *this street* -- which matches how
poker is spoken ("raise to 60").
"""

from utils import evaluator
from treys import Deck


class Player:
    def __init__(self, name, stack, is_hero=False):
        self.name = name
        self.stack = stack
        self.is_hero = is_hero
        self.hole = []          # treys card ints
        self.reset_for_hand()

    def reset_for_hand(self):
        self.hole = []
        self.folded = False
        self.all_in = False
        self.street_contrib = 0   # chips in this street
        self.total_contrib = 0    # chips in this hand
        self.acted = False        # has acted since the last bet/raise

    @property
    def in_hand(self):
        return not self.folded

    @property
    def contesting(self):
        """Still able to make a betting decision (not folded, not all-in)."""
        return not self.folded and not self.all_in


class PokerGame:
    STREETS = ["preflop", "flop", "turn", "river"]

    def __init__(self, num_opponents=2, starting_stack=1000, sb=10, bb=20,
                 hero_name="You"):
        self.sb = sb
        self.bb = bb
        self.players = [Player(hero_name, starting_stack, is_hero=True)]
        for i in range(num_opponents):
            self.players.append(Player(f"Seat {i + 1}", starting_stack))
        self.button = 0
        self.stage = "idle"
        self.board = []
        self.to_act = None
        self.current_bet = 0
        self.min_raise = bb
        self.pots = []        # list of (amount, [eligible player indices])
        self.results = []     # list of human-readable result lines
        self.log = []         # action history for the current hand

    # -- helpers ----------------------------------------------------------
    def n(self):
        return len(self.players)

    def pot(self):
        return sum(p.total_contrib for p in self.players)

    def in_hand_indices(self):
        return [i for i, p in enumerate(self.players) if p.in_hand]

    def contesting_indices(self):
        return [i for i, p in enumerate(self.players) if p.contesting]

    def to_call(self, idx):
        p = self.players[idx]
        return min(self.current_bet - p.street_contrib, p.stack)

    def _next_seat(self, start):
        """Next contesting seat at or after `start` (wraps)."""
        m = self.n()
        for k in range(m):
            i = (start + k) % m
            if self.players[i].contesting:
                return i
        return None

    # -- hand setup -------------------------------------------------------
    def start_hand(self):
        # players with no chips sit out; if too few, can't play
        for p in self.players:
            p.reset_for_hand()
        self.board = []
        self.deck = Deck()
        self.results = []
        self.log = []
        self.pots = []
        self.current_bet = 0
        self.min_raise = self.bb

        playable = [p for p in self.players if p.stack > 0]
        if len(playable) < 2:
            self.stage = "complete"
            self.results = ["Not enough players with chips."]
            return

        # deal two cards to everyone with chips
        for p in self.players:
            if p.stack > 0:
                p.hole = self.deck.draw(2)

        self._post_blinds()
        self.stage = "preflop"
        # first to act preflop
        if self.n() == 2:
            first = self.button                  # heads-up: button/SB acts first
        else:
            first = (self.button + 3) % self.n()  # UTG, left of BB
        self.to_act = self._next_seat(first)
        self._check_round_state(just_started=True)

    def _post_blinds(self):
        m = self.n()
        if m == 2:
            sb_pos, bb_pos = self.button, (self.button + 1) % m
        else:
            sb_pos, bb_pos = (self.button + 1) % m, (self.button + 2) % m
        self._post(sb_pos, self.sb)
        self._post(bb_pos, self.bb)
        self.current_bet = self.bb
        self.min_raise = self.bb
        # blinds don't count as "acted" -- they get their option
        for p in self.players:
            p.acted = False

    def _post(self, idx, amount):
        p = self.players[idx]
        amount = min(amount, p.stack)
        p.stack -= amount
        p.street_contrib += amount
        p.total_contrib += amount
        if p.stack == 0:
            p.all_in = True

    # -- legal actions ----------------------------------------------------
    def legal_actions(self, idx=None):
        """What the player to act may do. Amounts are 'raise to' totals."""
        if idx is None:
            idx = self.to_act
        if idx is None:
            return {}
        p = self.players[idx]
        call_amt = self.to_call(idx)
        can_check = call_amt == 0
        actions = {
            "fold": True,
            "check": can_check,
            "call": call_amt if call_amt > 0 else 0,
            "can_call": call_amt > 0,
        }
        # raising / betting
        max_to = p.street_contrib + p.stack            # all-in total
        if self.current_bet == 0:
            min_to = min(self.bb, max_to)              # min bet = one big blind
            actions["bet"] = True
            actions["raise"] = False
        else:
            min_to = self.current_bet + self.min_raise
            actions["bet"] = False
            actions["raise"] = True
        # can only raise if you have chips beyond a call
        can_aggress = p.stack > call_amt
        actions["can_raise"] = can_aggress
        actions["min_to"] = min(min_to, max_to)
        actions["max_to"] = max_to
        return actions

    # -- applying an action ----------------------------------------------
    def act(self, action, amount=None):
        idx = self.to_act
        if idx is None:
            raise RuntimeError("No player to act")
        p = self.players[idx]
        call_amt = self.to_call(idx)

        if action == "fold":
            p.folded = True
            p.acted = True
            self.log.append(f"{p.name} folds")

        elif action == "check":
            if call_amt != 0:
                raise ValueError("Cannot check facing a bet")
            p.acted = True
            self.log.append(f"{p.name} checks")

        elif action == "call":
            self._put(p, call_amt)
            p.acted = True
            tag = " (all-in)" if p.all_in else ""
            self.log.append(f"{p.name} calls {call_amt}{tag}")

        elif action in ("bet", "raise"):
            la = self.legal_actions(idx)
            if not la["can_raise"]:
                raise ValueError("Cannot raise")
            target = int(amount) if amount is not None else la["min_to"]
            target = max(la["min_to"], min(target, la["max_to"]))
            add = target - p.street_contrib
            self._put(p, add)
            raise_size = target - self.current_bet
            # a full raise re-opens action; a short all-in does not increase min_raise
            if raise_size >= self.min_raise:
                self.min_raise = raise_size
            self.current_bet = max(self.current_bet, target)
            for other in self.players:
                if other is not p and other.contesting:
                    other.acted = False
            p.acted = True
            verb = "bets" if action == "bet" else "raises to"
            tag = " (all-in)" if p.all_in else ""
            self.log.append(f"{p.name} {verb} {target}{tag}")
        else:
            raise ValueError(f"Unknown action {action}")

        self._advance()

    def _put(self, p, amount):
        amount = max(0, min(amount, p.stack))
        p.stack -= amount
        p.street_contrib += amount
        p.total_contrib += amount
        if p.stack == 0:
            p.all_in = True

    # -- progression ------------------------------------------------------
    def _advance(self):
        # hand ends immediately if only one player remains
        if len(self.in_hand_indices()) == 1:
            self._award_uncontested()
            return
        self._check_round_state()

    def _check_round_state(self, just_started=False):
        # find next player who still needs to act
        contesting = self.contesting_indices()
        need = [i for i in contesting
                if not self.players[i].acted
                or self.players[i].street_contrib < self.current_bet]

        if need and len(contesting) >= 1:
            # move action to the next such player after the current one
            start = (self.to_act + 1) % self.n() if not just_started else self.to_act
            nxt = self._first_needing(start)
            if nxt is not None:
                self.to_act = nxt
                return
        # betting round is closed
        self.to_act = None
        self._close_round()

    def _first_needing(self, start):
        m = self.n()
        for k in range(m):
            i = (start + k) % m
            p = self.players[i]
            if p.contesting and (not p.acted or p.street_contrib < self.current_bet):
                return i
        return None

    def _close_round(self):
        # reset street state
        for p in self.players:
            p.street_contrib = 0
            p.acted = False
        self.current_bet = 0
        self.min_raise = self.bb

        # if <2 players can still act, no more betting -- run it out
        if len(self.contesting_indices()) < 2:
            self._deal_to_showdown()
            return

        # otherwise advance to the next street
        if self.stage == "preflop":
            self._deal_board(3); self.stage = "flop"
        elif self.stage == "flop":
            self._deal_board(1); self.stage = "turn"
        elif self.stage == "turn":
            self._deal_board(1); self.stage = "river"
        elif self.stage == "river":
            self._showdown(); return

        # start the new betting round (first active left of the button)
        start = (self.button + 1) % self.n()
        self.to_act = self._next_seat(start)

    def _deal_board(self, count):
        cards = self.deck.draw(count)
        if not isinstance(cards, list):
            cards = [cards]
        self.board += cards

    def _deal_to_showdown(self):
        while len(self.board) < 5:
            self._deal_board(1)
        self._showdown()

    # -- awarding ---------------------------------------------------------
    def _award_uncontested(self):
        self.to_act = None
        winner = self.in_hand_indices()[0]
        amount = self.pot()
        self.players[winner].stack += amount
        self.pots = [(amount, [winner])]
        self.results = [f"{self.players[winner].name} wins {amount} "
                        "(everyone else folded)."]
        self.stage = "complete"

    def _build_pots(self):
        """Split contributions into main/side pots with eligible players."""
        contribs = {i: p.total_contrib for i, p in enumerate(self.players)
                    if p.total_contrib > 0}
        pots = []
        prev = 0
        for level in sorted(set(contribs.values())):
            layer = level - prev
            contributors = [i for i, c in contribs.items() if c >= level]
            amount = layer * len(contributors)
            eligible = [i for i in contributors if self.players[i].in_hand]
            if amount > 0:
                pots.append((amount, eligible))
            prev = level
        return pots

    def _showdown(self):
        self.to_act = None
        self.stage = "complete"
        pots = self._build_pots()
        self.pots = pots
        self.results = []

        for amount, eligible in pots:
            if not eligible:
                continue
            if len(eligible) == 1:
                win = eligible
            else:
                scores = {i: evaluator.evaluate(self.board, self.players[i].hole)
                          for i in eligible}
                best = min(scores.values())
                win = [i for i in eligible if scores[i] == best]
            share = amount // len(win)
            rem = amount - share * len(win)
            for j, i in enumerate(win):
                give = share + (1 if j < rem else 0)
                self.players[i].stack += give
            names = ", ".join(self.players[i].name for i in win)
            label = "main pot" if (amount, eligible) == pots[0] else "side pot"
            self.results.append(f"{names} win {amount} ({label}).")

    # -- queries ----------------------------------------------------------
    def hand_over(self):
        return self.stage == "complete"

    def hand_class(self, idx):
        from utils import hand_class
        return hand_class(self.players[idx].hole, self.board)

    def rotate_button(self):
        self.button = (self.button + 1) % self.n()
