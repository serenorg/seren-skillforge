---
name: polymarket-trader
description: "Rank opportunities from prediction market data and produce paper or live trading plans."
---

# Polymarket Trader

## When to Use

- find polymarket opportunities
- paper trade prediction markets

## Workflow Summary

1. `fetch_markets` uses `connector.market_data.get`
2. `score` uses `connector.model.post`
3. `choose` uses `transform.top_n`
4. `plan` uses `transform.create_plan`
