# ai-bench

Open, reproducible tests of local and cloud AI models: what each model is **good for** and **not good for**, how fast
it runs on each machine, and what it costs to buy or rent the hardware.

The videos are in Brazilian Portuguese at [ksay.com.br](https://ksay.com.br).

- **Use-case batteries** ([`cases/`](cases/)): coding (with automated tests), RAG (correct answer **and** the source
  passage cited), agents (tool calling and exact JSON schemas) and chat & summaries in Portuguese. Short, synthetic and
  identical for every model.
- **Verdict**: per-use-case scores over at least 3 runs, mapped to Good for / Not good for (≥ 80%). See
  [METHODOLOGY.md](METHODOLOGY.md).
- **Speed**: `llama-bench` at several context depths, with repetitions.
- **Cost**: buying vs renting a GPU per month, with the break-even point.

Python 3.11+ and the standard library only: nothing to install with pip.

```bash
python3 -m unittest discover -s tests -t .                       # free, no network
python3 -m aibench run --episode 03-is-bigger-better --machine mac-m5 --simulate --label dry-run
python3 -m aibench cost --example
```

How to run each episode on each machine, with time and cost estimates: [HOW-TO-RUN.md](HOW-TO-RUN.md).

## Episodes

| # | Folder | Question |
| --- | --- | --- |
| 1 | [`episodes/01-buy-or-rent-gpu`](episodes/01-buy-or-rent-gpu/) | Buy or rent a GPU to run AI? |
| 2 | [`episodes/02-what-runs-on-16gb-and-8gb`](episodes/02-what-runs-on-16gb-and-8gb/) | What runs on 16 GB and on 8 GB? |
| 3 | [`episodes/03-is-bigger-better`](episodes/03-is-bigger-better/) | Is a bigger model better? |

## Layout

```
aibench/      runner, checkers, verdict, speed, cost, environment, pre-publish check
cases/        the public use-case batteries
episodes/     one folder per episode: models, inputs and results (CSV)
tests/        offline tests (fake servers, fake llama-bench)
scripts/      pre-publish-check.sh
```

## License

Code: [MIT](LICENSE). Data (cases, prices, results): [CC BY 4.0](LICENSE-DATA).
