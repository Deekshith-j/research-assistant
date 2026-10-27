# Replay of planned queries (26 cases)

| strategy | mean gold recall | cases missing gold | evidence size |
|---|---|---|---|
| equal weights (baseline) | 0.923 | 3 ["R09:['release-22:0']", "R11:['incident-12:1', 'release-21:1']", "R25:['faq:1']"] | 8.0 |
| secondary weight 0.5 | 0.923 | 3 ["R09:['release-22:0']", "R11:['incident-12:1', 'release-21:1']", "R25:['faq:1']"] | 8.0 |
| equal weights + siblings | 0.962 | 2 ["R09:['release-22:0']", "R25:['faq:1']"] | 12.1 |
| secondary weight 0.5 + siblings | 0.962 | 2 ["R09:['release-22:0']", "R25:['faq:1']"] | 12.0 |
