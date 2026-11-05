# Execution simulator

Rough cost model for getting option and index orders filled.

What it does:
- **Market orders** pay half the spread plus square-root market impact: impact grows with volatility and with the square root of order size over daily volume.
- **Limit orders** wait in the queue and fill only when traded volume clears the quantity ahead of them.
- **Latency cost.** While an order travels, price moves like a random walk. The expected adverse move is vol x sqrt(latency) x sqrt(2/pi). The simulator compares a slow path (about 350 ms) against a fast one (about 5 ms) and the test checks the simulated saving against that formula.

At 15% annual volatility the saving from 350 ms to 5 ms is about a quarter of a basis point (see `BENCHMARKS.md`). It matters for high-turnover strategies, not for a few orders a day.

```bash
python -m unittest research_showcases.execution_simulator.test_microstructure
```

Limits: no real order book data; queue position and volume are inputs, not measured.
