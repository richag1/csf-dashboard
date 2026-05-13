# csf-dashboard

Public dashboard for a personal paper-trading experiment.

**Live site:** [Your GitHub Pages URL goes here]

## What this is

A small static site that shows the running performance of a personal
quant-strategy paper-trading experiment. Data refreshes daily after
US market close.

## What this is not

- Not investment advice
- Not a recommendation to buy or sell anything
- Not real money — this is a paper-trading log
- Not affiliated with any institution

## How it works

A separate (private) repository contains the strategy code and runs daily
via GitHub Actions. After each run, sanitised performance data (percentages
only, no dollar amounts) is committed to the `data/` folder of this repo,
and GitHub Pages serves it.

## Files

- `index.html` — the dashboard
- `data/summary.json` — top-level metrics
- `data/performance.json` — every signal's return and alpha
- `data/positions.json` — currently held paper positions
- `data/equity_curves.json` — daily cumulative return series
- `data/signals.json` — last-update metadata
