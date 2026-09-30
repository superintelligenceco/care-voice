# Alert rules

Each rule is a pure function that takes today's check-in, the recent history, and the thresholds from the `rules` section of the config, and returns an alert or nothing. Every alert carries a severity and the reasons behind it, quoting what the person said.

| Code | Severity | Triggers when |
| --- | --- | --- |
| `EMERGENCY_WORDS` | critical | Any reply contains phrases such as "help me", "can't breathe", "chest pain", "can't get up", or "on the floor". The agent also tells the person to call their local emergency number. |
| `NO_ANSWER` | high, critical on a streak | Nobody answers after `checkin.call_attempts` tries. Critical when the previous check-in was also unanswered. |
| `CHECKIN_INCOMPLETE` | medium | The call ends, or the person goes silent, before all questions are answered. |
| `FALL_REPORTED` | high | The person says yes to the fall question, or mentions falling, tripping, or slipping in any reply. |
| `MISSED_MEDS` | high | The person says they have not taken their morning medication. |
| `MEDS_UNCONFIRMED` | medium | The medication answer stays unclear after re-prompting. |
| `PAIN_REPORTED` | medium, high at `rules.pain_high_threshold` (7) | The person reports pain. The alert includes the level and location when given. |
| `POSSIBLE_CONFUSION` | medium, high with 2+ signs | Any of: wrong or unknown day of the week, disoriented phrases ("where am I"), the same reply of `rules.repetition_min_words` (4) or more words repeated, or `rules.unclear_answers_threshold` (2) or more unclear answers. |
| `MOOD_DROP` | medium | Mood is at least `rules.mood_drop_threshold` (1.5) points below the average of the last `rules.baseline_window` (14) check-ins, once there are `rules.baseline_min_checkins` (3). |
| `LOW_MOOD` | low | Mood is `rules.low_mood_threshold` (2) or below and no drop alert fired. |
| `NOT_EATEN` | low | The person has not eaten yet. |
| `POOR_SLEEP` | low | The person did not sleep well. |

These rules are simple heuristics, not clinical assessments. Tune the thresholds for the person and review the alerts with them and their caregivers.
