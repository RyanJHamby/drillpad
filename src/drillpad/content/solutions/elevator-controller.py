# ruff: noqa
class ElevatorController:
    def __init__(self, num_floors, start=0):
        self.num_floors = num_floors
        self.floor = start
        self.direction = "idle"
        self._stops = set()

    @property
    def stops(self):
        return sorted(self._stops)

    def request(self, floor):
        if not 0 <= floor < self.num_floors:
            raise ValueError(floor)
        self._stops.add(floor)

    def _choose_direction(self):
        above = [s for s in self._stops if s > self.floor]
        below = [s for s in self._stops if s < self.floor]
        if self.direction == "up" and above:
            return "up"
        if self.direction == "down" and below:
            return "down"
        if above and below:
            near_up = min(above) - self.floor
            near_down = self.floor - max(below)
            if self.direction == "idle":
                return "up" if near_up <= near_down else "down"
            return "down" if self.direction == "up" else "up"
        if above:
            return "up"
        if below:
            return "down"
        return "idle"

    def step(self):
        if self.floor in self._stops:
            self._stops.discard(self.floor)
            return ("open", self.floor)
        if not self._stops:
            self.direction = "idle"
            return ("idle", self.floor)
        self.direction = self._choose_direction()
        self.floor += 1 if self.direction == "up" else -1
        return ("move", self.floor)
