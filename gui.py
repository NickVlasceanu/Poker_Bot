"""Pop-out interactive Texas Hold'em with a live coach.

A full game on a green felt canvas: you click Fold / Check / Call / Bet / Raise,
the equity-driven opponents act on their own, and the side panel coaches every
one of your decisions (pot odds, equity, EV, outs, implied odds, recommendation).

Run:  python gui.py
"""

import queue
import threading
import tkinter as tk
from tkinter import font as tkfont

import coach
import opponent
from engine import PokerGame
from utils import advise, card_to_str

# --- palette ---------------------------------------------------------------
FELT = "#0b6623"
FELT_DARK = "#08501b"
CARD_FACE = "#fdfdfd"
CARD_BACK = "#2c3e72"
CARD_EDGE = "#cccccc"
TEXT_LIGHT = "#f4f4f4"
GOLD = "#ffd54a"
RED = "#d62828"
BLACK = "#1a1a1a"
DIM = "#8fae8f"
ACTIVE = "#ffe082"

SUIT_SYMBOL = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}
RED_SUITS = {"h", "d"}

CARD_W, CARD_H = 64, 90
MINI_W, MINI_H = 38, 54
W, H = 980, 560
AI_DELAY = 800  # ms between AI actions so you can follow the action


class PokerTable:
    def __init__(self, root, num_opponents=2):
        self.root = root
        self.num_opponents = num_opponents
        self.root.title("Hold'em Coach")
        self.root.configure(bg=FELT_DARK)

        self.canvas = tk.Canvas(root, width=W, height=H, bg=FELT,
                                highlightthickness=0)
        self.canvas.pack(padx=12, pady=(12, 6))

        self._build_action_bar()
        self._build_coach_panel()

        self.rank_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.suit_font = tkfont.Font(family="Segoe UI", size=24)
        self.mini_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.big_font = tkfont.Font(family="Segoe UI", size=15, weight="bold")

        self._coach_q = queue.Queue()
        self._coach_token = 0
        self.root.after(80, self._poll_coach)

        self.game = PokerGame(num_opponents=self.num_opponents)
        self.new_hand()

    # -- widgets ----------------------------------------------------------
    def _build_action_bar(self):
        bar = tk.Frame(self.root, bg=FELT_DARK)
        bar.pack(fill="x", padx=12, pady=(0, 6))

        self.fold_btn = tk.Button(bar, text="Fold", width=10,
                                  command=self.do_fold)
        self.fold_btn.pack(side="left", padx=3)
        self.call_btn = tk.Button(bar, text="Check", width=12,
                                  command=self.do_call)
        self.call_btn.pack(side="left", padx=3)

        self.raise_scale = tk.Scale(bar, from_=0, to=100, orient="horizontal",
                                    length=220, bg=FELT_DARK, fg=TEXT_LIGHT,
                                    highlightthickness=0, troughcolor="#0a7a28",
                                    showvalue=True)
        self.raise_scale.pack(side="left", padx=(10, 3))
        self.raise_btn = tk.Button(bar, text="Raise", width=10,
                                   command=self.do_raise)
        self.raise_btn.pack(side="left", padx=3)
        for label, frac in (("½ Pot", 0.5), ("Pot", 1.0), ("All-in", None)):
            tk.Button(bar, text=label, width=6,
                      command=lambda f=frac: self._preset(f)).pack(side="left", padx=2)

        self.next_btn = tk.Button(bar, text="Next Hand ↻", width=12,
                                  command=self.new_hand, state="disabled")
        self.next_btn.pack(side="right", padx=3)
        tk.Label(bar, text="Opponents:", bg=FELT_DARK,
                 fg=TEXT_LIGHT).pack(side="right")
        self.opp_var = tk.IntVar(value=self.num_opponents)
        tk.Spinbox(bar, from_=1, to=6, width=3, textvariable=self.opp_var,
                   command=self.change_opponents).pack(side="right", padx=4)

    def _build_coach_panel(self):
        frame = tk.Frame(self.root, bg=FELT_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(frame, text="COACH — why this play", bg=FELT_DARK, fg=GOLD,
                 anchor="w").pack(fill="x")
        body = tk.Frame(frame, bg=FELT_DARK)
        body.pack(fill="both", expand=True)
        self.coach_text = tk.Text(body, height=15, width=116, wrap="word",
                                  bg="#10241a", fg="#e6efe6",
                                  font=("Consolas", 10), relief="flat",
                                  padx=12, pady=8)
        sb = tk.Scrollbar(body, command=self.coach_text.yview)
        self.coach_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.coach_text.pack(side="left", fill="both", expand=True)
        self.coach_text.configure(state="disabled")

    def set_coach(self, text):
        self.coach_text.configure(state="normal")
        self.coach_text.delete("1.0", "end")
        self.coach_text.insert("1.0", text)
        self.coach_text.configure(state="disabled")

    # -- game control -----------------------------------------------------
    def change_opponents(self):
        self.num_opponents = self.opp_var.get()
        self.game = PokerGame(num_opponents=self.num_opponents)
        self.new_hand()

    def new_hand(self):
        if self.game.players[0].stack <= 0 or \
                sum(1 for p in self.game.players if p.stack > 0) < 2:
            self.game = PokerGame(num_opponents=self.num_opponents)
        self.game.start_hand()
        self.next_btn.config(state="disabled")
        self.process_turn()

    def process_turn(self):
        if self.game.hand_over():
            self._finish_hand()
            return
        idx = self.game.to_act
        self.render()
        if idx == 0:
            self._hero_turn()
        else:
            self._set_buttons(False)
            self.root.after(AI_DELAY, self._ai_act)

    def _ai_act(self):
        idx = self.game.to_act
        if idx is None or idx == 0 or self.game.hand_over():
            self.process_turn()
            return
        action, amount = opponent.choose(self.game, idx)
        self.game.act(action, amount)
        self.process_turn()

    def _hero_turn(self):
        la = self.game.legal_actions(0)
        self._set_buttons(True, la)
        self._request_coach()

    def _finish_hand(self):
        self._set_buttons(False)
        self.next_btn.config(state="normal")
        self.render(reveal=True)
        lines = list(self.game.results)
        hero = self.game.players[0]
        if not hero.folded and len(self.game.in_hand_indices()) > 1:
            lines.append(f"Your hand: {self.game.hand_class(0)}")
        lines.append("")
        lines.append("Bankroll lesson: judge each decision by whether your equity "
                     "beat the price you paid — not by whether this one hand won.")
        self.set_coach("\n".join(lines))

    # -- hero actions -----------------------------------------------------
    def do_fold(self):
        if self.game.to_act == 0:
            self.game.act("fold")
            self.process_turn()

    def do_call(self):
        if self.game.to_act != 0:
            return
        la = self.game.legal_actions(0)
        self.game.act("check" if la["check"] else "call")
        self.process_turn()

    def do_raise(self):
        if self.game.to_act != 0:
            return
        la = self.game.legal_actions(0)
        if not la["can_raise"]:
            return
        target = int(self.raise_scale.get())
        self.game.act("bet" if la["bet"] else "raise", target)
        self.process_turn()

    def _preset(self, frac):
        la = self.game.legal_actions(0)
        if not la["can_raise"]:
            return
        if frac is None:
            target = la["max_to"]
        else:
            target = self.game.current_bet + round(self.game.pot() * frac)
            if la["bet"]:
                target = round(self.game.pot() * frac)
        target = max(la["min_to"], min(target, la["max_to"]))
        self.raise_scale.set(target)

    def _set_buttons(self, on, la=None):
        state = "normal" if on else "disabled"
        self.fold_btn.config(state=state)
        self.call_btn.config(state=state)
        if on and la:
            self.call_btn.config(
                text="Check" if la["check"] else f"Call {la['call']}")
            if la["can_raise"]:
                self.raise_btn.config(
                    state="normal", text="Bet" if la["bet"] else "Raise")
                self.raise_scale.config(state="normal",
                                        from_=la["min_to"], to=la["max_to"])
                self.raise_scale.set(la["min_to"])
            else:
                self.raise_btn.config(state="disabled")
                self.raise_scale.config(state="disabled")
        else:
            self.raise_btn.config(state="disabled")
            self.raise_scale.config(state="disabled")

    # -- coach (off the UI thread) ---------------------------------------
    def _request_coach(self):
        self.set_coach("Calculating equity, pot odds and implied odds...")
        self._coach_token += 1
        token = self._coach_token
        g = self.game
        hole = [card_to_str(c) for c in g.players[0].hole]
        cards = [card_to_str(c) for c in g.board]
        opp_in = max(1, len(g.in_hand_indices()) - 1)
        to_call = g.to_call(0)
        pot = g.pot()
        behind = self._behind()

        def work():
            eq = advise(hole, cards, opp_in, iterations=700)
            text = coach.coach(eq, to_call, pot, cards, hole, opp_in, behind=behind)
            self._coach_q.put((token, text))

        threading.Thread(target=work, daemon=True).start()

    def _poll_coach(self):
        try:
            while True:
                token, text = self._coach_q.get_nowait()
                if token == self._coach_token:
                    self.set_coach(text)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_coach)

    def _behind(self):
        hero = self.game.players[0]
        opp = [p.stack for i, p in enumerate(self.game.players)
               if i != 0 and p.in_hand and not p.all_in]
        return min(hero.stack, max(opp)) if opp else 0

    # -- drawing ----------------------------------------------------------
    def _face(self, x, y, card_str, w, h, rfont, sfont):
        rank = "10" if card_str[0].upper() == "T" else card_str[0].upper()
        sl = card_str[1].lower()
        color = RED if sl in RED_SUITS else BLACK
        sym = SUIT_SYMBOL[sl]
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=CARD_FACE,
                                     outline=CARD_EDGE, width=2)
        self.canvas.create_text(x + 10, y + 12, text=rank, fill=color, font=rfont)
        self.canvas.create_text(x + w / 2, y + h / 2 + 3, text=sym, fill=color,
                                font=sfont)
        self.canvas.create_text(x + w - 10, y + h - 12, text=rank, fill=color,
                                font=rfont)

    def _back(self, x, y, w, h):
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=CARD_BACK,
                                     outline=CARD_EDGE, width=2)
        self.canvas.create_text(x + w / 2, y + h / 2, text="♠", fill="#3d4f8a",
                                font=self.label_font)

    def _slot(self, x, y, w, h):
        self.canvas.create_rectangle(x, y, x + w, y + h, outline="#0a7a28",
                                     width=2, dash=(3, 3))

    def render(self, reveal=False):
        self.canvas.delete("all")
        g = self.game

        # pot + last action
        self.canvas.create_text(W / 2, 16, text=f"POT  {g.pot()}", fill=GOLD,
                                font=self.big_font)
        if g.log:
            self.canvas.create_text(W / 2, 38, text=g.log[-1], fill=TEXT_LIGHT,
                                    font=self.label_font)

        # opponents across the top
        opps = [i for i in range(g.n()) if i != 0]
        seat_w = 150
        total = len(opps) * seat_w
        x0 = (W - total) / 2
        for slot, i in enumerate(opps):
            self._draw_seat(g, i, x0 + slot * seat_w, 60, reveal)

        # community board
        self.canvas.create_text(W / 2, 250, text="", fill=TEXT_LIGHT)
        cards = [card_to_str(c) for c in g.board]
        gap = 10
        bw = 5 * CARD_W + 4 * gap
        bx = (W - bw) / 2
        for k in range(5):
            x = bx + k * (CARD_W + gap)
            if k < len(cards):
                self._face(x, 230, cards[k], CARD_W, CARD_H,
                           self.rank_font, self.suit_font)
            else:
                self._slot(x, 230, CARD_W, CARD_H)

        # hero
        hero = g.players[0]
        hl = ACTIVE if g.to_act == 0 else TEXT_LIGHT
        self.canvas.create_text(W / 2, 360,
                                text=f"YOU   stack {hero.stack}   bet "
                                     f"{hero.street_contrib}", fill=hl,
                                font=self.label_font)
        hcards = [card_to_str(c) for c in hero.hole]
        hw = 2 * CARD_W + gap
        hx = (W - hw) / 2
        for k, c in enumerate(hcards):
            self._face(hx + k * (CARD_W + gap), 375, c, CARD_W, CARD_H,
                       self.rank_font, self.suit_font)
        if g.button == 0:
            self.canvas.create_text(hx - 16, 420, text="Ⓓ", fill=GOLD,
                                    font=self.big_font)

    def _draw_seat(self, g, i, sx, sy, reveal):
        p = g.players[i]
        active = (g.to_act == i)
        folded = p.folded
        name_color = DIM if folded else (ACTIVE if active else TEXT_LIGHT)

        # cards
        cx = sx + 18
        for k in range(2):
            x = cx + k * (MINI_W + 6)
            if folded:
                self._slot(x, sy, MINI_W, MINI_H)
            elif reveal and not folded:
                self._face(x, sy, card_to_str(p.hole[k]), MINI_W, MINI_H,
                           self.mini_font, self.label_font)
            else:
                self._back(x, sy, MINI_W, MINI_H)

        self.canvas.create_text(sx + 55, sy + MINI_H + 14, text=p.name,
                                fill=name_color, font=self.label_font)
        info = f"stack {p.stack}"
        if p.street_contrib:
            info += f"   bet {p.street_contrib}"
        if p.all_in:
            info += "  ALL-IN"
        self.canvas.create_text(sx + 55, sy + MINI_H + 32, text=info,
                                fill=name_color, font=self.mini_font)
        if active:
            self.canvas.create_rectangle(sx + 4, sy - 6, sx + 116,
                                         sy + MINI_H + 44, outline=ACTIVE, width=2)
        if g.button == i:
            self.canvas.create_text(sx + 104, sy - 2, text="Ⓓ", fill=GOLD,
                                    font=self.label_font)


def main():
    root = tk.Tk()
    PokerTable(root)
    root.mainloop()


if __name__ == "__main__":
    main()
