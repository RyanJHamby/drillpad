# ruff: noqa
def pacific_atlantic(heights):
    if not heights or not heights[0]:
        return []
    R, C = len(heights), len(heights[0])
    def fill(starts):
        seen = set(starts)
        stack = list(starts)
        while stack:
            r, c = stack.pop()
            for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                if 0 <= nr < R and 0 <= nc < C and (nr, nc) not in seen and heights[nr][nc] >= heights[r][c]:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
        return seen
    pac = fill([(0, c) for c in range(C)] + [(r, 0) for r in range(1, R)])
    atl = fill([(R-1, c) for c in range(C)] + [(r, C-1) for r in range(R-1)])
    return [[r, c] for r, c in pac & atl]
