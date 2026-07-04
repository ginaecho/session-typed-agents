# Integration stress suite — generated complex cases

**Verdict: FAILURES PRESENT** — 2105/2110 checks over 100 seeded iterations (2481.5s, Scribble judging throughout).

Each iteration generates a fresh 4-7-role protocol with nested choices, then runs the five stages described in `experiments/scripts/integration_stress.py` (round-trip, mutation catch, critic oracle, revisor loop, incremental chain).

| check | pass rate |
|---|---|
| `S1.generated_protocol_scribble_valid` | 100/100 |
| `S1.local_types_recompose` | 100/100 |
| `S1.message_set_preserved` | 100/100 |
| `S1.recomposition_scribble_valid` | 100/100 |
| `S2.mutation_caught` | 95/100 |
| `S3.reversed_precedence_fails` | 100/100 |
| `S3.taint_reachable_flagged` | 92/92 |
| `S3.taint_unreachable_clean` | 21/21 |
| `S3.true_precedence_passes` | 100/100 |
| `S4.critic_fails_broken` | 97/97 |
| `S4.revisor_accepts_scripted_fix` | 97/97 |
| `S4.setup` | 3/3 |
| `S5.extension_0_blast_radius` | 100/100 |
| `S5.extension_0_child_cache_hit` | 100/100 |
| `S5.extension_0_monitor_bad` | 100/100 |
| `S5.extension_0_monitor_good` | 100/100 |
| `S5.extension_0_valid` | 100/100 |
| `S5.extension_1_blast_radius` | 100/100 |
| `S5.extension_1_child_cache_hit` | 100/100 |
| `S5.extension_1_monitor_bad` | 100/100 |
| `S5.extension_1_monitor_good` | 100/100 |
| `S5.extension_1_valid` | 100/100 |
| `gen.shape` | 100/100 |

