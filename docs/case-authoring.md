# Case authoring

Write each first-round case as one JSON file in `cases/`. A case should work
from either side. Complete the private facts and proof mappings before
writing the questions so the logic stays consistent through a replay.

## Case contents

| Group | What to author |
| --- | --- |
| Identity | Stable case ID, display title, format version, and the fictional jurisdiction. |
| Opening | Police briefing, explicitly attributed statements, and exhibit IDs already disclosed. |
| Charge | The legal elements as defined in this fictional jurisdiction, their required proof combinations, material contradictions, and possible resolutions. |
| Private facts | What actually happened, the timeline, and plausible competing explanations. Give referenced claims stable IDs. |
| Leads | Stable IDs, location or topic aliases, prerequisites, and the evidence or witness profiles each lead reveals. |
| Exhibits | Display title, text, provenance, claims supported or challenged, and any foundation the case requires. |
| Witnesses | Public profile, manner of speaking, private motivations, what they personally know, and allowed statements. For each conditional statement, record what allows the witness to say it. |
| Rival | Ordered witness choices and exhibits for each side, their disclosures, and the normal examination moves. Give occasional departures a specific objection ground and a normal alternative. |
| Sentencing | Baseline sentence, minimum sentence, and mitigation factors linked to admissible proof. |

An allowed witness statement can be truthful, mistaken, evasive, or a lie,
depending on what that witness knows and wants. Every statement has stable
text and a stable ID. Give a few variations when a witness's attitude might
change. Link each statement to the claims it supports or challenges. For
example, a witness can offer a personal observation and then change their
account after an authenticated exhibit is shown. Keep both accounts as
separate statements with their own eligibility conditions.

## Small example

In **The Annex Ledger**, police report that a city ledger was missing at
closing and that archivist Neri was assigned the last shift. The report
allows two explanations. Neri deliberately took the ledger, or a second
person borrowed the key and moved it without Neri knowing.

- Investigating the key cabinet reveals a sign-out log and a clerk who can
  explain how it was kept.
- The clerk says who signed out the key. The log cannot establish who
  actually entered the room. A separate observation would be needed for
  that link.
- A caretaker saw a person in a pale coat near the annex. They can describe
  the coat and time. The case gives them no firsthand basis for naming the
  person.
- During the caretaker's direct examination, the rival could ask, “You saw
  Neri take it, didn't you?” A leading objection should be sustained. On
  cross-examination, a leading objection to that wording alone should be
  overruled. An objection about personal knowledge is a different question.

The example shows how to build leads and objection opportunities. The first
playable case needs a complete timeline, cast, and proof map.

## Review before enabling a case

- Check that the briefing discloses only its listed exhibits and statements.
- Walk all investigation paths that can reach the budget. Confirm the player
  can choose two witnesses and the rival still has two distinct choices.
- Confirm every reveal, statement condition, exhibit, and proof combination
  refers to an existing case ID.
- Play one route to a supported conviction and one to an acquittal. Confirm
  that the case can also demonstrate a reduced sentence after conviction.
- Check that a rejected or struck item cannot satisfy a proof combination.
