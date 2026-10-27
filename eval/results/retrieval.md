# Retrieval evaluation (26 cases with gold chunks)

| mode | recall@4 | recall@8 | all gold@4 | all gold@8 | MRR |
|---|---|---|---|---|---|
| vector | 0.885 | 0.962 | 0.846 | 0.962 | 0.891 |
| bm25 | 0.904 | 0.942 | 0.846 | 0.923 | 0.885 |
| hybrid | 0.885 | 0.981 | 0.846 | 0.962 | 0.879 |

## vector: cases missing a gold chunk in the top 8 (1)

- R11 (incident): missed ['incident-12:1', 'release-21:1']; got ['incident-03:0', 'incident-12:0', 'incident-08:0', 'incident-08:1', 'release-23:1', 'incident-03:2', 'release-20:1', 'incident-12:2']

## bm25: cases missing a gold chunk in the top 8 (2)

- R25 (unanswerable): missed ['faq:1']; got ['pricing:0', 'onboarding:1', 'release-23:2', 'onboarding:0', 'traces:0', 'oncall:0', 'handbook:0', 'release-23:1']
- R26 (unanswerable): missed ['security:2']; got ['company:0', 'security:0', 'faq:0', 'regions:0', 'export:2', 'traces:1', 'oncall:1', 'traces:0']

## hybrid: cases missing a gold chunk in the top 8 (1)

- R25 (unanswerable): missed ['faq:1']; got ['pricing:0', 'oncall:0', 'release-23:2', 'pricing:2', 'release-21:0', 'handbook:1', 'handbook:0', 'ingest:1']
