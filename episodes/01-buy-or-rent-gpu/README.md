# Episode 1: Buy or rent a GPU to run AI?

Monthly cost of buying a card vs renting one on RunPod (on demand or always on), the break-even in hours of use per
month, and what the same models do on each rented card: speed and the Good for / Not good for verdict.

## Inputs

- `prices.csv`: card prices and hourly rental prices, each with a source, date and `status` (FILL_IN → CONFIRMED).
- `assumptions.csv`: exchange rate, electricity rate, hours of use, amortization and setup time per session.
- `prices.example.csv` and `assumptions.example.csv`: fictional values to test the formula (`--example`).
- `models.toml`: the models run on every rented card.

## Outputs (`results/`)

- `cost.csv`: `buy`, `rent_on_demand` and `rent_always_on` per option, in BRL per month, and the break-even.
- `speed.csv`: tokens per second for prompt processing (pp) and generation (tg) per card and depth.
- `scores.csv`, `verdicts.csv`, `verdicts.md`: per-use-case scores and verdicts per card and model.

The formula is in [`aibench/cost.py`](../../aibench/cost.py). Commands: [HOW-TO-RUN.md](../../HOW-TO-RUN.md).
