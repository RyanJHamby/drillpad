# ruff: noqa
import heapq


class Twitter:
    def __init__(self):
        self.clock = 0
        self.tweets = {}
        self.following = {}

    def post_tweet(self, user_id, tweet_id):
        self.tweets.setdefault(user_id, []).append((self.clock, tweet_id))
        self.clock += 1

    def get_news_feed(self, user_id):
        users = set(self.following.get(user_id, ())) | {user_id}
        heap = []
        for u in users:
            lst = self.tweets.get(u)
            if lst:
                heap.append((-lst[-1][0], u, len(lst) - 1))
        heapq.heapify(heap)
        out = []
        while heap and len(out) < 10:
            _, u, i = heapq.heappop(heap)
            lst = self.tweets[u]
            out.append(lst[i][1])
            if i > 0:
                heapq.heappush(heap, (-lst[i - 1][0], u, i - 1))
        return out

    def follow(self, follower_id, followee_id):
        if follower_id != followee_id:
            self.following.setdefault(follower_id, set()).add(followee_id)

    def unfollow(self, follower_id, followee_id):
        self.following.get(follower_id, set()).discard(followee_id)
