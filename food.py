"""Der Snack: ein Stueck Futter, das einfach auf dem Desktop liegt.

Anders als der Ball (`ball.py`) hat der Snack keine Physik — er faellt nicht und
prallt nicht, er liegt an seiner Position, bis ein Pet ihn frisst. `Snack` ist
reine Logik: eine Position, ein `eaten`-Flag und die Notiz, welcher Pet ihn
gerade ansteuert, damit nicht mehrere gleichzeitig hinlaufen. Das Overlay
zeichnet ihn (siehe render.draw_snack), die Pets lesen seine Position.
"""


class Snack:
    def __init__(self, x, y):
        # (x, y) ist der Snack-Mittelpunkt in globalen Bildschirmkoordinaten.
        self.x = float(x)
        self.y = float(y)
        self.eaten = False
        # Der Pet, der gerade herlaeuft (per Objekt-Identitaet), oder None. Nur
        # eine Notiz zur Koordination in main.py — verhindert den Doppel-Ansturm.
        self.claimed_by = None

    def claimed(self):
        """Ob aktuell noch ein lebender, hungriger Pet den Snack ansteuert."""
        pet = self.claimed_by
        if pet is None:
            return False
        return pet.snack_target is self
