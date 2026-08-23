class ChaosVenue:
    """Small fake venue for fail-closed and reconnect safety tests."""

    def __init__(self):
        self.unsafe = False
        self.reason = None
        self.remote_positions = {}
        self.local_positions = {}

    def partition(self, reason: str):
        self.unsafe = True
        self.reason = reason

    def entry(self, symbol: str, price: float):
        if self.unsafe:
            raise PermissionError("new entries blocked while venue is unsafe")
        self.local_positions[symbol] = 1
        return {"status": "entered", "symbol": symbol, "price": price}

    def protective_close(self, symbol: str, quantity: float):
        self.local_positions.pop(symbol, None)
        return {"status": "closed", "symbol": symbol, "quantity": quantity, "reduce_only": True}

    def reconnect(self):
        self.local_positions = dict(self.remote_positions)
        self.unsafe = False
        self.reason = None
