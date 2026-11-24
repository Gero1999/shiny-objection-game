# Game design

Shiny Objection is a fictional criminal trial game. The player investigates a
case, chooses a witness, and argues either for the prosecution or for the
defense. A good round lets the player identify why they won or lost and what
they would do differently on a replay.

## From briefing to verdict

| Phase | Player decisions | Game behavior |
| --- | --- | --- |
| Connection | Enter a hosted model token or connect to Ollama. | Check the selected model before starting the round. |
| Briefing | Read the opening police report and choose a side. | Randomly select an authored case and show only the opening disclosures. Attribute observations and allegations to their sources. |
| Defense consultation | Ask your client what happened and where to investigate. | Reveal authored client accounts outside the trial record. |
| Investigation | Describe what to search, inspect, or ask about. | Match the request to an authored lead. Reveal the linked evidence and witness profiles. |
| Witness selection | Choose one witness from the discovered profiles. | Lock the player's selection and pick a different witness for the rival. |
| Trial | Question witnesses, present exhibits, object, and reply to objections. | Alternate direct and cross-examination, rule on pending moves, and maintain the admitted record. |
| Closing and verdict | Connect admitted testimony and exhibits to the elements of the charge. | Explain whether the evidence meets the fictional burden for each element. |
| Sentencing | After a conviction, argue about the sentence. | Apply case-defined mitigation supported by the admitted record. |

For the first case, start with three successful investigations. An already
completed lead, an unmatched request, or a clarification costs no
investigation. The player can stop once they have found at least two
witnesses. The case must allow every path that reaches the investigation
limit to uncover at least two selectable witnesses.

At the start of trial, show both lineups and disclose the rival's public
witness profiles and exhibit list. Keep their private accounts and motives
out of the briefing. Each side has access to its own exhibits plus material
disclosed during trial according to the case. Disclosure makes material
available to reference. Admission determines what the jury can consider.

## Witness rounds

The prosecution calls its witness first, followed by the defense.
For each witness, the calling side conducts direct examination and the
other side conducts cross-examination.

- During their examination, the player can ask a question in plain language,
  offer an available exhibit in chat, or end the examination.
- During the rival's examination, reveal one authored question or exhibit
  offer at a time. Pause for the player to pass or object before the witness
  answers or the exhibit takes effect.
- The rival can object to a player move. The player can state the purpose
  of the question or explain the exhibit's foundation before the ruling.
- Objections to a provisional answer may be raised before it enters the
  admitted record. A sustained objection to a question blocks the answer.
  A sustained objection to testimony strikes the affected answer.

The player can follow up in their own words. The witness's response draws on
their authored knowledge, personality, and current stance. A hesitant
witness might deny a fact until confronted with a particular admitted
exhibit. Contradictions, evasion, and lies are possibilities defined by the
case author. Keep private motives and internal stance labels off the screen.

### Occasional rival misconduct

Author ordinary sequences for the rival's direct and cross-examinations.
Mark optional departures in a few places across those sequences. A departure
can be a leading question, an unsupported allegation, or an attempt to
introduce an exhibit without laying a foundation. Play at most two such
departures in a trial and avoid consecutive departures. Seed their selection
so a test or recorded demo can reproduce a particular hearing.

Across the case library, give each supported objection ground its own authored
opportunity. A single trial only needs a small sample.

The prompt should give the player a chance to spot the issue. Avoid marking
improper moves as such before the ruling. Include legitimate but pointed
questions, too, so objecting to everything is a poor way to read the trial.
The prototype's acceptance example includes a valid sustained objection
and a plausible objection that the judge overrules.

## Fictional objection rules

Show a short rule reference in the courtroom. The player selects a ground
from the dropdown and clicks **Object**. The side whose move was challenged
gets one reply. The judge explains the ruling using the rule and relevant
part of the pending move or record.

| Ground | Sustain when |
| --- | --- |
| Leading | A question suggests its own answer during direct examination. A leading question on cross can proceed if that is the only ground. |
| Hearsay | A party offers an out-of-court statement to prove what the statement asserts. The judge can overrule if the record supports a different purpose, such as showing what notice the witness received. |
| Speculation | The question asks the witness to assert something outside their personal knowledge. |
| Relevance | The stated purpose has no supported link to an element of the charge, an exhibit, or a witness's credibility. |
| Lack of foundation | The offered exhibit lacks the supporting testimony or authentication required by its case definition. |

An overruled objection lets the move proceed. A sustained objection stops
the question, excludes the exhibit, or strikes the affected answer. The
transcript can still show that the ruling occurred. Passing on an objection
lets a structurally valid move proceed under the game's rules. The strength
of the underlying proof is a separate judgment. Testimony admitted for a
limited purpose supports only that purpose when the jury evaluates it.

## Verdict and sentence

In the first case, the charge has a small set of elements. Each element has
one or more combinations of authored proof that can satisfy it. Convict
only when the admitted record completes a combination for every element
and resolves any contradictions in that record that the case marks as
material to an element. Otherwise acquit. Cite the exhibit numbers and
testimony lines that mattered, including the missing proof on acquittal.

The rival gives a short closing before the player's. Closing arguments let the player identify the relevant links between the
record and their theory. An argument can call attention to evidence already
in the record. The jury scores the supported links to the elements.

After a conviction, the fictional court applies the case's baseline sentence
and considers any supported mitigation. A defense win can be an acquittal
or a reduced sentence. The prosecution sees whether it secured a
conviction and why the sentence changed.

## First playable case

Start with one original case, one charge, four witnesses, and two plausible
explanations of the facts. Use a small set of leads and exhibits that a
player can learn in one sitting. Play it from both sides with a fake model
before tuning the dialogue. The first playtest should answer whether a
different investigation or witness choice can produce a different outcome
for reasons visible in the record.

See [Case authoring](case-authoring.md) for the information each case needs.
