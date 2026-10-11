# ruff: noqa
class ParkingLot:
    SIZES = ["small", "medium", "large"]
    FITS = {"motorcycle": ["small", "medium", "large"], "car": ["medium", "large"], "truck": ["large"]}
    RATE = {"small": 1, "medium": 2, "large": 4}

    def __init__(self, spots):
        self.free = {s: spots.get(s, 0) for s in self.SIZES}
        self.tickets = {}      # id -> (plate, size, start)
        self.plates = set()
        self.next_id = 1

    def park(self, plate, vehicle_type, now):
        if vehicle_type not in self.FITS:
            raise ValueError(vehicle_type)
        if plate in self.plates:
            raise ValueError("already parked")
        for size in self.FITS[vehicle_type]:
            if self.free[size] > 0:
                self.free[size] -= 1
                tid = self.next_id
                self.next_id += 1
                self.tickets[tid] = (plate, size, now)
                self.plates.add(plate)
                return tid
        return None

    def unpark(self, ticket_id, now):
        plate, size, start = self.tickets.pop(ticket_id)   # KeyError if unknown
        self.plates.discard(plate)
        self.free[size] += 1
        hours = max(1, -(-(now - start) // 3600))
        return self.RATE[size] * hours

    def available(self):
        return dict(self.free)

    def spot_of(self, ticket_id):
        return self.tickets[ticket_id][1]
