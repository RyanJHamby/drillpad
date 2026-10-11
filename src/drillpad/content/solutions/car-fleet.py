# ruff: noqa
def car_fleet(target, position, speed):
    cars = sorted(zip(position, speed), reverse=True)
    fleets = 0
    lead = 0.0
    for p, s in cars:
        t = (target - p) / s
        if t > lead:
            fleets += 1
            lead = t
    return fleets
