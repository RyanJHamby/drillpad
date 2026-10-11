import httpx

from drillpad.anki.scheduler import DueCard


class AnkiConnectError(RuntimeError):
    pass


class AnkiConnect:
    """Anki stays the source of truth for scheduling; requires Anki running with AnkiConnect."""

    def __init__(self, url: str = "http://127.0.0.1:8765", client: httpx.Client | None = None):
        self.url = url
        self.client = client or httpx.Client(timeout=5)

    def _call(self, action: str, **params):
        try:
            body = self.client.post(self.url, json={"action": action, "version": 6, "params": params}).json()
        except httpx.HTTPError as e:
            raise AnkiConnectError(f"cannot reach AnkiConnect at {self.url}: {e}") from e
        if body.get("error"):
            raise AnkiConnectError(body["error"])
        return body["result"]

    def due(self, queries: dict[str, list[str]], include_new: bool = False) -> list[DueCard]:
        cards: dict[int, DueCard] = {}
        for problem_id, qs in queries.items():
            for q in qs:
                for cid in self._call("findCards", query=f"({q}) (is:due OR is:new)" if include_new else f"({q}) is:due"):
                    cards.setdefault(cid, DueCard(cid, problem_id))
        return list(cards.values())

    def answer(self, card_id: int, ease: int) -> None:
        self._call("answerCards", answers=[{"cardId": card_id, "ease": ease}])
