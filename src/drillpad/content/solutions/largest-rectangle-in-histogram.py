# ruff: noqa
def largest_rectangle_area(heights):
    st = []
    best = 0
    hs = list(heights) + [0]
    for i, h in enumerate(hs):
        while st and hs[st[-1]] >= h:
            top = hs[st.pop()]
            left = st[-1] if st else -1
            best = max(best, top * (i - left - 1))
        st.append(i)
    return best
