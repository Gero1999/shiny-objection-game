# Working on Shiny Objection

Shiny Objection is a fictional courtroom game designed for Shiny for Python.
Read [README.md](README.md) for the player flow and current project status.
Use the [game design](docs/game-design.md) for phase and ruling behavior and
the [case authoring guide](docs/case-authoring.md) when editing case content.
Read the [technical architecture](docs/architecture.md) for module boundaries,
session state, and the first implementation slice.

## Gameplay invariants

- Keep the case's facts, exhibits, witness accounts, and possible discoveries
  in authored case data. Keep the current playthrough's discoveries and trial
  record in separate session state.
- Reveal the police briefing first. Limit later player views to information
  unlocked by investigation or disclosed during trial.
- Give each side a turn to examine its witnesses and the other side a chance
  to cross-examine. Provide an objection window before a challengeable move
  can affect testimony or the trial record.
- Base rulings and verdicts on the game's fictional rules and validated game
  state. The verdict should explain what the admitted record established.

## Implementation guidance

- Keep game rules and case parsing independent of Shiny and model providers
  so they can be tested with scripted inputs.
- Use one model interface for a player-supplied hosted token and an Ollama
  connection. Keep hosted tokens in the server session, outside case files,
  saved games, and logs.
- Treat player text and model output as input to validate. Resolve references
  against the current case and phase before applying any changes.
- Test the transitions that can break a playthrough, including premature
  disclosures, an exhibit that was never discovered, a sustained objection,
  and testimony that was struck from the record. Use a fake model adapter for
  repeatable tests.
- Write original cases and characters set in the game's fictional jurisdiction.
