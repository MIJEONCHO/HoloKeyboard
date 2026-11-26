"""Five small, vector-drawn moles. All effects stay in this Canvas."""
import math

MOLE_SECONDS = 2.8


class MoleEffect:
    def __init__(self, canvas, scale, sfx, on_score, skip_label, rng=None):
        self.canvas, self.scale, self.sfx = canvas, scale, sfx
        self.on_score, self.skip_label = on_score, skip_label
        self.score = self.errors = 0
        self.active = self.celebrating = False
        self.t0 = self.now = 0.0
        self.moles = []
        self.draw()

    def draw(self):
        c, s = self.canvas, self.scale
        c.delete("moles", "fx")
        hits = [m["hit"] for m in self.moles]
        self.moles = []
        width = int(c.cget("width"))
        ground = int(c.cget("height")) - 17*s
        for index in range(5):
            cx = width*(index+.5)/5
            tag = f"mole{index}"

            def oval(x1, y1, x2, y2, color, *, fixed=False):
                tags = ("moles",) if fixed else ("moles", tag)
                return c.create_oval(cx+x1*s, ground+y1*s, cx+x2*s, ground+y2*s,
                                     fill=color, outline="", tags=tags)

            def line(points, color):
                coords = [v for x, y in points for v in (cx+x*s, ground+y*s)]
                return c.create_line(*coords, fill=color, width=max(1, 3*s),
                                     smooth=True, capstyle="round", tags=("moles", tag))

            oval(-44, -6, 44, 14, "#0a1712", fixed=True)
            oval(-34, -70, -10, -46, "#9a6c49")
            oval(10, -70, 34, -46, "#9a6c49")
            oval(-36, -76, 36, 8, "#bd8f68")
            oval(-25, -40, 25, 5, "#efd0a5")
            oval(-8, -37, 8, -27, "#593b2c")
            eyes = [oval(x-4, -50, x+4, -38, "#2c1f1b") for x in (-13, 13)]
            cheeks = [oval(x-6, -34, x+6, -27, "#edaa92") for x in (-25, 25)]
            smile = line([(-11,-20), (0,-8), (11,-20)], "#593b2c")
            frown = line([(-11,-11), (0,-23), (11,-11)], "#593b2c")
            brows = [line([(-23,-56),(-8,-51)], "#593b2c"),
                     line([(8,-51),(23,-56)], "#593b2c")]
            tears = [oval(x-5, -36, x+5, -17, "#75d8ff") for x in (-19,19)]
            oval(-44, 2, 44, 15, "#10221a", fixed=True)
            c.tag_bind(tag, "<Button-1>", lambda _e, i=index: self.whack(i))
            self.moles.append(dict(cx=cx, ground=ground, tag=tag, y=0, eyes=eyes,
                                   cheeks=cheeks, brows=brows, tears=tears, smile=smile,
                                   frown=frown, hit=hits[index] if hits else None))
        self.set_errors(self.errors)

    def set_errors(self, count):
        self.errors = max(0, min(5, count))
        for i, mole in enumerate(self.moles):
            sad = i < self.errors
            for key, visible in (("cheeks", not sad), ("smile", not sad), ("brows", sad),
                                 ("frown", sad), ("tears", sad and self.errors >= 3)):
                items = mole[key] if isinstance(mole[key], list) else (mole[key],)
                for item in items:
                    self.canvas.itemconfigure(item, state="normal" if visible else "hidden")

    def start(self, now, celebrate=False):
        self.now = self.t0 = now
        self.active, self.celebrating = True, celebrate
        self.set_errors(0)
        for mole in self.moles:
            mole["hit"] = None
        self.canvas.delete("fx")
        self.canvas.create_text(int(self.canvas.cget("width"))-8*self.scale, 6*self.scale,
                                text=self.skip_label(), anchor="ne", fill="#a6c8b5",
                                font=("Malgun Gothic", -max(8, round(11*self.scale))), tags=("fx","skip"))
        self.canvas.tag_bind("skip", "<Button-1>", lambda _e: self.stop())
        for index, mole in enumerate(self.moles):
            if celebrate or index % 2 == 0:
                self._star(mole)

    def _star(self, mole):
        self.canvas.create_text(mole["cx"], mole["ground"]-85*self.scale, text="✦",
                                fill="#ffe2a0", font=("Malgun Gothic", -round(20*self.scale)), tags=("fx",))

    def whack(self, index):
        mole = self.moles[index]
        if not self.active or mole["hit"] is not None:
            return
        mole["hit"] = self.now
        self.score += 1
        self._star(mole)
        self.sfx.play("pop")
        self.on_score(self.score)

    def step(self, now):
        self.now = now
        elapsed = now-self.t0
        if self.active and elapsed >= MOLE_SECONDS:
            self.stop()
        for i, mole in enumerate(self.moles):
            bob = math.sin(now*2.5+i*.72)*2.8
            if self.active:
                bob -= (8 if self.celebrating else 5)*abs(math.sin(elapsed*4+i*.47))
                if mole["hit"] is not None:
                    bob += 14*max(0.0, 1-(now-mole["hit"])/.45)
            y = round(bob*self.scale, 1)
            blink = (now+i*.67) % 4.8 < .14
            if y != mole["y"]:
                self.canvas.move(mole["tag"], 0, y-mole["y"])
                mole["y"] = y
            if blink != mole.get("blink"):
                mole["blink"] = blink
                for item in mole["eyes"]:
                    x1, _, x2, _ = self.canvas.coords(item)
                    center = mole["ground"]-44*self.scale+y
                    half = (1 if blink else 6)*self.scale
                    self.canvas.coords(item, x1, center-half, x2, center+half)
        return self.active

    def resize(self, scale):
        self.scale = scale
        self.draw()
        if self.active:
            for mole in self.moles:
                if self.celebrating or mole["hit"] is not None:
                    self._star(mole)

    def stop(self):
        was = self.active
        self.active = self.celebrating = False
        self.canvas.delete("fx")
        return was
