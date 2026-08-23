from collections import deque
from decimal import Decimal


class EdgeDecayMonitor:
    def __init__(self, window: int = 20, compression_ratio: Decimal = Decimal("0.5")):
        if window < 2 or not (Decimal("0") < compression_ratio < Decimal("1")):
            raise ValueError("invalid edge monitor settings")
        self.window = window
        self.compression_ratio = compression_ratio
        self.values = deque(maxlen=window * 2)
        self.derisk = False

    def record(self, expectancy: Decimal) -> None:
        self.values.append(Decimal(expectancy))
        if len(self.values) >= self.window * 2:
            baseline = sum(list(self.values)[:self.window]) / Decimal(self.window)
            recent = sum(list(self.values)[-self.window:]) / Decimal(self.window)
            if baseline > 0 and recent < baseline * self.compression_ratio:
                self.derisk = True
