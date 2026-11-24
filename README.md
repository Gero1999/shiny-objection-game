<div align="center">
  <img src="static/logo.svg" width="128" height="128" alt="Gold gavel with blue sparks inside a dark teal speech bubble">
  <h1>Shiny Objection</h1>
  <p><strong>Follow the evidence. Question the witnesses. Make your case.</strong></p>
  <p>A fictional courtroom game built with Shiny for Python. Play as the prosecutor or the defense attorney and see what you can prove in court.</p>
  <p><a href="#the-annex-ledger">The first case</a> · <a href="#run-the-game">Run the game</a> · <a href="#dialogue-modes">Dialogue modes</a> · <a href="#project-docs">Project docs</a></p>
</div>

## The Annex Ledger

A civic ledger is missing at closing. The shift record puts an archivist on
duty, but the police report can’t say who moved it. A key cabinet, a hallway
clock, and a dry-store receipt offer different ways into the case.

If you play defense, you can first talk privately with your client about what happened and where to look.

| Stage | Your move |
| --- | --- |
| **Briefing** | Read the police report and choose prosecution or defense. |
| **Investigation** | Describe a lead in your own words. Collect exhibits and choose one witness to call. |
| **Trial** | Question your witness, cross-examine the rival’s, and type an offer such as “Offer the handoff receipt.” Object to improper moves and respond when opposing counsel objects. |
| **Verdict** | Make a closing argument. The jury explains its verdict from the admitted record. If there’s a conviction, the court considers mitigation. |

Investigation messages have a 240-character limit. The chat returns the evidence and witness profiles for the matched lead.

> **Try a lead.** Enter “check the key cabinet,” then ask the clerk who kept
> the register. Establishing its source gives you a foundation to offer it
> as evidence.

The rival gives their closing first. Your reply can be up to 480 characters.

## Run the game

Requires Python 3.11 or later. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m shiny run app.py
```

Open the local URL shown by Shiny and choose a dialogue mode. **Scripted
practice** is the quickest way to play the full case.

## Dialogue modes

| Mode | Setup |
| --- | --- |
| **Scripted practice** | Works without credentials. Matches questions to authored testimony. |
| **Ollama** | Run Ollama and enter the name of an installed model. For a small connection test, pull `smollm2:135m`. The app defaults to `http://127.0.0.1:11434`. Use `SHINY_OBJECTION_OLLAMA_URL` on the Shiny server to configure another endpoint. [Ollama setup](https://github.com/ollama/ollama) |
| **OpenAI** | Enter your API token and a model that supports structured outputs. The default is the lower-cost `gpt-4.1-nano`. The server holds the token for your session, and calls may use API credits. |

For a trusted local run, set `SHINY_OBJECTION_OPENAI_KEY` before starting
Shiny if you prefer to keep the key out of the browser. Otherwise, the token field
is available on localhost or over HTTPS. The password field masks the key on
screen. Shiny receives a browser-entered key and uses it to authenticate to
OpenAI, so use a server you trust.

Model modes use the active witness’s eligible statements and recent exchanges
to select an authored answer. The game applies objection rules and decides the
outcome from the trial record.

## Project docs

- [Game design](docs/game-design.md) explains the player flow and rules of the fictional court.
- [Case authoring](docs/case-authoring.md) covers how evidence, witnesses, and testimony fit together.
- [Technical architecture](docs/architecture.md) describes the engine, Shiny session, and model adapters.
- [Development guide](AGENTS.md) records the gameplay and testing conventions.

Run the engine tests from the repository root.

```bash
python -m unittest discover -s tests -v
```

Open an issue for a gameplay idea or start a branch and submit a pull request.
