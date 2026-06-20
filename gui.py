"""Pop-out poker table -- a Tkinter window version of the ASCII game.

Draws real card graphics on a green felt canvas and lets you step through a
hand with buttons instead of watching it scroll past in the terminal.

Run:  python gui.py
"""

import queue
import threading
import tkinter as tk
from tkinter import font as tkfont

from utils import (
    advise, deal_hand, showdown_winner, hand_class, card_to_str,
)

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
GREEN_BAR = "#37c24a"
YELLOW_BAR = "#e8c33a"
RED_BAR = "#d6452d"

SUIT_SYMBOL = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}
RED_SUITS = {"h", "d"}

CARD_W, CARD_H = 70, 98
STREETS = [("Pre-flop", 0), ("Flop", 3), ("Turn", 4), ("River", 5)]


class PokerTable:
    def __init__(self, root, num_opponents=2):
        self.root = root
        self.num_opponents = num_opponents
        self.root.title("Poker Equity Bot")
        self.root.configure(bg=FELT_DARK)

        self.canvas = tk.Canvas(root, width=920, height=560,
                                bg=FELT, highlightthickness=0)
        self.canvas.pack(padx=12, pady=(12, 6))

        self._build_controls()

        self.rank_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.suit_font = tkfont.Font(family="Segoe UI", size=26)
        self.label_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.big_font = tkfont.Font(family="Segoe UI", size=15, weight="bold")

        # Worker threads push equity results here; the main thread polls it so
        # no Tk call ever happens off the main thread (Tkinter isn't thread-safe).
        self._equity_q = queue.Queue()
        self._equity_token = 0  # ignore results from superseded calculations
        self.root.after(80, self._poll_equity)

        self.new_hand()

    # -- controls ----------------------------------------------------------
    def _build_controls(self):
        bar = tk.Frame(self.root, bg=FELT_DARK)
        bar.pack(fill="x", padx=12, pady=(0, 12))

        self.next_btn = tk.Button(bar, text="Next Street ▶",
                                  command=self.next_street, width=16)
        self.next_btn.pack(side="left", padx=4)

        tk.Button(bar, text="New Hand ↻", command=self.new_hand,
                  width=14).pack(side="left", padx=4)

        tk.Label(bar, text="Opponents:", bg=FELT_DARK,
                 fg=TEXT_LIGHT).pack(side="left", padx=(16, 2))
        self.opp_var = tk.IntVar(value=self.num_opponents)
        tk.Spinbox(bar, from_=1, to=6, width=3, textvariable=self.opp_var,
                   command=self.new_hand).pack(side="left")

    # -- game flow ---------------------------------------------------------
    def new_hand(self):
        self.num_opponents = self.opp_var.get()
        self.hero, self.opponents, self.full_board = deal_hand(self.num_opponents)
        self.hero_str = [card_to_str(c) for c in self.hero]
        self.board_str = [card_to_str(c) for c in self.full_board]
        self.street_idx = 0
        self.pot = 20 * (self.num_opponents + 1)
        self.revealed = False
        self.next_btn.config(text="Next Street ▶", state="normal")
        self.render()
        self.update_equity()

    def next_street(self):
        if self.street_idx < len(STREETS) - 1:
            self.street_idx += 1
            self.pot += 40 * (self.num_opponents + 1)
            if self.street_idx == len(STREETS) - 1:
                self.next_btn.config(text="Showdown ♠")
            self.render()
            self.update_equity()
        else:
            self.showdown()

    def showdown(self):
        self.revealed = True
        self.next_btn.config(state="disabled")
        result, seat = showdown_winner(self.hero, self.opponents, self.full_board)
        hero_cls = hand_class(self.hero, self.full_board)
        if result == "hero":
            msg, color = f"YOU WIN {self.pot} chips!  ({hero_cls})", GOLD
        elif result == "tie":
            msg, color = f"SPLIT POT with Seat {seat + 1}  ({hero_cls})", YELLOW_BAR
        else:
            msg, color = f"Seat {seat + 1} wins.  You had {hero_cls}.", RED
        self.render(banner=(msg, color))

    # -- equity (off the UI thread so the window stays responsive) ----------
    def update_equity(self):
        n = STREETS[self.street_idx][1]
        shown = self.board_str[:n]
        self.canvas.itemconfigure("equity_text", text="Calculating equity...")

        self._equity_token += 1
        token = self._equity_token

        def work():
            eq = advise(self.hero_str, shown, self.num_opponents, iterations=600)
            self._equity_q.put((token, eq))

        threading.Thread(target=work, daemon=True).start()

    def _poll_equity(self):
        """Main-thread drain of finished equity calcs; reschedules itself."""
        try:
            while True:
                token, eq = self._equity_q.get_nowait()
                if token == self._equity_token:  # newest request only
                    self.draw_equity(eq)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_equity)

    # -- drawing -----------------------------------------------------------
    def _card(self, x, y, card_str=None, face_up=True):
        """Draw one card with top-left corner at (x, y)."""
        if not face_up:
            self.canvas.create_rectangle(x, y, x + CARD_W, y + CARD_H,
                                         fill=CARD_BACK, outline=CARD_EDGE, width=2)
            for i in range(1, 5):
                gx = x + i * CARD_W / 5
                self.canvas.create_line(gx, y + 6, gx, y + CARD_H - 6,
                                        fill="#3d4f8a")
            return

        if card_str is None:  # empty placeholder slot
            self.canvas.create_rectangle(x, y, x + CARD_W, y + CARD_H,
                                         outline="#0a7a28", width=2, dash=(4, 4))
            return

        rank = "10" if card_str[0].upper() == "T" else card_str[0].upper()
        suit_letter = card_str[1].lower()
        color = RED if suit_letter in RED_SUITS else BLACK
        symbol = SUIT_SYMBOL[suit_letter]

        self.canvas.create_rectangle(x, y, x + CARD_W, y + CARD_H,
                                     fill=CARD_FACE, outline=CARD_EDGE, width=2)
        self.canvas.create_text(x + 12, y + 14, text=rank, fill=color,
                                font=self.rank_font, anchor="center")
        self.canvas.create_text(x + 12, y + 30, text=symbol, fill=color,
                                font=self.label_font, anchor="center")
        self.canvas.create_text(x + CARD_W / 2, y + CARD_H / 2 + 4, text=symbol,
                                fill=color, font=self.suit_font, anchor="center")
        self.canvas.create_text(x + CARD_W - 12, y + CARD_H - 14, text=rank,
                                fill=color, font=self.rank_font, anchor="center")

    def _row(self, cards, y, count=None, face_up=True):
        """Center a row of cards horizontally on the canvas at height y."""
        n = count if count is not None else len(cards)
        gap = 12
        total = n * CARD_W + (n - 1) * gap
        x0 = (920 - total) / 2
        for i in range(n):
            card = cards[i] if i < len(cards) else None
            self._card(x0 + i * (CARD_W + gap), y, card, face_up)

    def render(self, banner=None):
        self.canvas.delete("all")
        street = STREETS[self.street_idx][0]
        n = STREETS[self.street_idx][1]

        # title + pot
        self.canvas.create_text(460, 22, text=street.upper(), fill=TEXT_LIGHT,
                                font=self.big_font)
        self.canvas.create_text(820, 22, text=f"Pot: {self.pot}", fill=GOLD,
                                font=self.label_font)

        # opponents
        self.canvas.create_text(120, 60, text=f"Opponents ({self.num_opponents})",
                                fill=TEXT_LIGHT, font=self.label_font, anchor="w")
        if self.revealed:
            flat = []
            for opp in self.opponents:
                flat += [card_to_str(c) for c in opp]
            self._row(flat, 74, face_up=True)
        else:
            self._row([], 74, count=self.num_opponents * 2, face_up=False)

        # community board
        self.canvas.create_text(120, 210, text="Community", fill=TEXT_LIGHT,
                                font=self.label_font, anchor="w")
        self._row(self.board_str[:n], 224, count=5)

        # hero
        self.canvas.create_text(120, 350, text="Your hand", fill=GOLD,
                                font=self.label_font, anchor="w")
        self._row(self.hero_str, 364, face_up=True)

        # equity placeholders (filled by draw_equity)
        self.canvas.create_text(460, 486, text="", fill=TEXT_LIGHT,
                                font=self.label_font, tags="equity_text")
        self.canvas.create_rectangle(310, 500, 610, 522, outline="#0a7a28",
                                     tags="equity_bar_bg")
        self.canvas.create_text(460, 540, text="", fill=TEXT_LIGHT,
                                font=self.label_font, tags="rec_text")

        if banner:
            msg, color = banner
            self.canvas.create_rectangle(160, 470, 760, 552, fill=FELT_DARK,
                                         outline=color, width=3)
            self.canvas.create_text(460, 511, text=msg, fill=color,
                                    font=self.big_font)

    def draw_equity(self, eq):
        if self.revealed:
            return
        self.canvas.delete("equity_fill")
        win, tie, e = eq["win"], eq["tie"], eq["equity"]
        self.canvas.itemconfigure(
            "equity_text",
            text=f"Win {win:.0%}    Tie {tie:.0%}    Equity {e:.0%}")
        color = GREEN_BAR if e >= 0.5 else YELLOW_BAR if e >= 0.3 else RED_BAR
        self.canvas.coords("equity_bar_bg", 310, 500, 610, 522)
        self.canvas.create_rectangle(310, 500, 310 + 300 * e, 522,
                                     fill=color, outline="", tags="equity_fill")
        self.canvas.itemconfigure(
            "rec_text",
            text=f"➔ {eq['recommendation']}   "
                 f"(fair share {eq['fair_share']:.0%})")


def main():
    root = tk.Tk()
    PokerTable(root)
    root.mainloop()


if __name__ == "__main__":
    main()
