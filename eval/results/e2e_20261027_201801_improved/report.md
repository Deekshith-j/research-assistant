# End-to-end evaluation (2026-10-27 20:35)

## Research

- **Passed: 26/27**
- Mean retrieval recall of gold chunks: 0.96
- Citations valid: 27/27 · cites gold: 26/27 · content correct: 27/27 · abstention correct: 27/27
- Mean latency: 22.9s · turns needing a revision: 4

| id | category | status | recall | cites valid | cites gold | content | abstain | pass |
|---|---|---|---|---|---|---|---|---|
| R01 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R02 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R03 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R04 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R05 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R06 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R07 | lookup | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R08 | multi-hop | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R09 | multi-hop | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R10 | multi-hop | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R11 | incident | answered | 0.5 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R12 | incident | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R13 | incident | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R14 | incident | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R15 | incident | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R16 | conflict | answered | 1.0 | ✅ | ❌ | ✅ | ✅ | ❌ |
| R17 | conflict | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R18 | temporal | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R19 | temporal | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R20 | temporal | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R21 | false-premise | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R22 | false-premise | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R23 | false-premise | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R24 | unanswerable | answered | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R25 | unanswerable | answered | 0.5 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R26 | unanswerable | insufficient_evidence | 1.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| R27 | unanswerable | insufficient_evidence | None | ✅ | ✅ | ✅ | ✅ | ✅ |

## Memory

- **Passed: 10/10**

- ✅ M01 Profile remembered across sessions and used to personalise
- ✅ M02 Answer preference is stored as a preference
- ✅ M03 Correction replaces the old memory and changes later answers
- ✅ M04 Forget request removes the memory, its history and audit text
- ✅ M05 One user's private context is never exposed to another user
- ✅ M06 Secrets are never stored or echoed
- ✅ M07 A remembered claim is not treated as company evidence
- ✅ M08 Follow-up question resolved from conversation history
- ✅ M09 Sensitive personal information is not stored
- ✅ M10 Forget everything
