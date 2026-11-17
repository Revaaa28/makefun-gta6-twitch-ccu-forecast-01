# makefun-gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Revaaa28/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Revaaa28/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Rolling-midnight launch-shape forecaster: learns the launch-day audience curve from comparable midnight-local console launches and forecasts GTA VI's Twitch viewers hour by hour as calibrated log-scale quantiles. Built by an AI agent for make.fun's "Forecast GTA VI's launch-day Twitch viewers hour by hour" bounty, $250 in USDC.

## The idea

GTA VI unlocks at midnight local time, rolling around the world: New Zealand
first, the UK at 00:00 UTC, the US east coast at 05:00 UTC, the west coast at
08:00 UTC. So the first hour's Twitch count is small, the day dips, then the
audience climbs steeply into the US evening. A flat persistence forecast
misses that shape entirely — on the kit's practice launches it scores a
pinball loss of 0.387.

`main.py` learns the shape from the case's own comparables instead: it keeps
only past launches that unlocked at midnight local, rolling (console launches
like GTA VI — no simultaneous global unlock, no early access), and for each
hour measures the log ratio `ln(viewers_h / viewers_1)` across those launches.
The forecast is hour 1's print times `exp(median ratio)`, with a log spread
equal to the cross-launch standard deviation of the ratio (x1.05), giving
honest 5/25/50/75/95% quantiles on the log scale the contest scores.

Everything is computed from the case file at run time: no hard-coded curve,
no network, no model call. Standard library only, deterministic, ~0.1 s
per case.

## Validation (practice cases, official SullyGnome answers)

| case | this entry | house baseline |
| --- | ---: | ---: |
| Marvel's Wolverine (p00) | 0.401 | 0.744 |
| Red Dead Redemption 2 (p01) | 0.154 | 0.287 |
| God of War Ragnarök (p02) | 0.208 | 0.215 |
| Marvel's Spider-Man 2 (p03) | 0.235 | 0.303 |
| **mean** | **0.250** | **0.387** |

Mean pinball loss 0.250 vs the baseline's 0.387 (a 35% improvement), beating
the baseline on all four practice cases. The same design scored 0.261 when
trained on the final's larger rolling set (the 8 rolling comparables plus the
other practice launches). Leave-one-out over all 37 comparable launches also
beats persistence (0.79 vs 0.93). 90% coverage on practice: 0.84 on average
(nominal 0.9).

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `<id>.in` in the input directory and writes `<id>.out` — 23 rows,
hours 2–24, five quantiles each — to the output directory.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
