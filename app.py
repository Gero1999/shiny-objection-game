"""Shiny front end for the scripted first case."""

import asyncio
import os
import secrets
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from shiny_objection.cases import Ground, Side, load_case, select_case
from shiny_objection.game import Game, GameError, Phase, PlayerView
from shiny_objection.hosted_model import DEFAULT_HOSTED_MODEL, OpenAIDialogue
from shiny_objection.models import Dialogue, ModelError, ScriptedDialogue, verify_connection
from shiny_objection.ollama import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, OllamaDialogue
from shiny_objection.outcome import SentenceResult, Verdict, deliberate, sentence
from shiny_objection.trial import QuestionRequest, Status, Trial


ROOT = Path(__file__).resolve().parent
CASES = tuple(load_case(path) for path in sorted((ROOT / "cases").glob("*.json")))


def briefing(view: PlayerView):
    return ui.div(
        ui.h2("Police briefing"),
        ui.p(view.briefing, class_="briefing-text"),
        ui.h3("Choose your side"),
        ui.div(
            ui.div(
                ui.input_action_button("prosecution", "Play prosecution", class_="btn-primary"),
                ui.p("Use the record to establish each element of the charge."),
            ),
            ui.div(
                ui.input_action_button("defense", "Play defense", class_="btn-outline-primary"),
                ui.p("Test the evidence, raise doubt, and argue mitigation."),
            ),
            class_="role-options",
        ),
    )


def investigation(view: PlayerView):
    return ui.div(
        ui.h2("Investigation"),
        ui.p(f"Remaining investigation leads · {view.investigations_left}", class_="status-line"),
        ui.p("Find at least two witnesses. Describe one place, record, or person to investigate."),
        ui.input_text("lead", "Lead to investigate", placeholder="Check the key cabinet", width="100%"),
        ui.div(
            ui.input_action_button("investigate", "Investigate", class_="btn-primary"),
            ui.input_action_button("finish_investigation", "Choose witnesses", class_="btn-outline-primary"),
            class_="actions",
        ),
    )


def choose_witnesses(view: PlayerView):
    return ui.div(
        ui.h2("Choose witnesses"),
        ui.input_checkbox_group(
            "witnesses", "Choose two witnesses to call",
            {witness.id: witness.name for witness in view.witnesses},
        ),
        ui.input_action_button("start_trial", "Start trial", class_="btn-primary"),
    )


def courtroom(view: PlayerView, trial: Trial, waiting: bool, draft_question: str):
    turn = trial.turn
    assert turn is not None
    witness = next(person for person in view.witnesses if person.id == turn.witness_id)
    return ui.div(
        ui.p(
            f"{turn.acting_side.value.title()} · {turn.examination.value.title()} examination",
            class_="status-line",
        ),
        ui.h2(witness.name),
        ui.p("Waiting for the witness model…", role="status")
        if waiting else courtroom_controls(view, trial, draft_question),
    )


def courtroom_controls(view: PlayerView, trial: Trial, draft_question: str):
    pending = trial.pending
    if pending is not None:
        move = ui.div(
            ui.p(pending.move.kind.value.title(), class_="status-line"),
            ui.p(pending.move.text),
            class_="pending-move",
        )
        if trial.player_turn:
            return ui.div(
                ui.p(f"Rival objection: {pending.objection.value}", class_="objection-label"),
                move,
                ui.input_text_area("reply_text", "Your reply", width="100%", rows=2),
                ui.input_action_button("reply", "Ask the judge to rule", class_="btn-primary"),
            )
        options = {ground.value: ground.value for ground in Ground}
        return ui.div(
            move,
            ui.input_select("ground", "Objection ground", options),
            ui.input_text("objection_reason", "Reason (optional)", width="100%"),
            ui.div(
                ui.input_action_button("object", "Object", class_="btn-primary"),
                ui.input_action_button("pass_move", "Let it proceed", class_="btn-outline-primary"),
                class_="actions",
            ),
            ui.tags.details(
                ui.tags.summary("Court rules"),
                ui.tags.ul(
                    ui.tags.li("Leading questions may be challenged during direct examination."),
                    ui.tags.li("Hearsay is a statement from outside court offered to prove what it says."),
                    ui.tags.li("Speculation calls for a guess outside the witness’s knowledge."),
                    ui.tags.li("Relevant questions connect to the charge, evidence, or credibility."),
                    ui.tags.li("Some exhibits need a witness to establish their foundation."),
                ),
                class_="exhibit",
            ),
        )
    if not trial.player_turn:
        return ui.input_action_button("rival_next", "Hear rival’s next move", class_="btn-primary")

    exhibits = {"": "Choose an exhibit", **{item.id: item.title for item in view.exhibits}}
    return ui.div(
        ui.input_text_area("question", "Question for the witness", value=draft_question, width="100%", rows=2),
        ui.input_action_button("ask", "Ask question", class_="btn-primary"),
        ui.div(
            ui.input_select("exhibit", "Exhibit", exhibits, width="100%"),
            ui.input_action_button("offer", "Offer exhibit", class_="btn-outline-primary"),
            class_="offer-row",
        ),
        ui.input_action_button("end_exam", "End examination", class_="btn-outline-primary"),
    )


def closing(trial: Trial):
    options = {
        str(entry.number): f"#{entry.number} · {entry.speaker}: {entry.text[:75]}"
        for entry in trial.record if entry.status == Status.ADMITTED and entry.proof_id is not None
    }
    return ui.div(
        ui.h2("Closing argument"),
        ui.input_text_area("closing_text", "Address the jury", width="100%", rows=4),
        ui.input_selectize("citations", "Cite admitted record entries (optional)", options, multiple=True, width="100%"),
        ui.input_action_button("deliberate", "Hear the verdict", class_="btn-primary"),
    )


def verdict_view(trial: Trial, verdict: Verdict, sentence_result: SentenceResult | None):
    winner = Side.PROSECUTION if verdict.convicted else Side.DEFENSE
    result = "Convicted" if verdict.convicted else "Acquitted"
    winner_name = "You" if trial.side == winner else "The rival"
    outcome = "a conviction" if verdict.convicted else "an acquittal"
    findings = []
    for finding in verdict.findings:
        findings.append(ui.tags.li(
            ui.strong(finding.element),
            ui.p("Proven" if finding.proven else "Reasonable doubt", class_="finding-state"),
            ui.tags.ul(*(
                ui.tags.li(f"#{entry.number} · {entry.text}") for entry in finding.evidence
            )) if finding.evidence else ui.p("The admitted record did not establish this element."),
            *(ui.p(f"Unresolved testimony #{entry.number}: {entry.text}") for entry in finding.unresolved),
        ))
    return ui.div(
        ui.p("Jury verdict", class_="status-line"),
        ui.h2(result),
        ui.p(f"{winner_name} secured {outcome}."),
        ui.tags.details(
            ui.tags.summary("Your closing argument"),
            ui.p(verdict.closing_argument),
            ui.p("Citations: " + ", ".join(f"#{item.number}" for item in verdict.closing_citations))
            if verdict.closing_citations else None,
            class_="exhibit",
        ),
        ui.tags.ul(*findings, class_="findings"),
        sentencing_view(trial, verdict, sentence_result),
    )


def sentencing_view(trial: Trial, verdict: Verdict, sentence_result: SentenceResult | None):
    options = verdict.sentencing
    if options is None:
        return ui.input_action_button("restart", "Play another round", class_="btn-primary")
    if sentence_result is not None:
        return ui.div(
            ui.h3("Sentence"),
            ui.p(f"{sentence_result.duration} {sentence_result.unit}"),
            ui.p(f"Reduced from {sentence_result.baseline} after mitigation.")
            if sentence_result.duration < sentence_result.baseline else None,
            *(
                ui.p(f"{factor.label} · " + ", ".join(f"#{entry.number}" for entry in factor.evidence))
                for factor in sentence_result.factors
            ),
            ui.input_action_button("restart", "Play another round", class_="btn-primary"),
        )
    factors = {
        factor.label: (
            f"{factor.label} ({' and '.join(f'#{entry.number}' for entry in factor.evidence)})"
        )
        for factor in options.factors
    }
    if factors and trial.side == Side.DEFENSE:
        contest = ui.input_checkbox_group("mitigation", "Ask for a reduction based on the record", factors)
    elif factors:
        contest = ui.tags.ul(*(ui.tags.li(value) for value in factors.values()))
    else:
        contest = ui.p("The admitted record supports no mitigation.")
    return ui.div(
        ui.h3("Sentencing"),
        ui.p(f"Baseline: {options.baseline} {options.unit}."),
        contest,
        ui.input_action_button("sentence", "Hear the sentence", class_="btn-primary"),
    )


def case_file(view: PlayerView):
    return ui.tags.aside(
        ui.h2("Case file"),
        ui.tags.details(ui.tags.summary("Police briefing"), ui.p(view.briefing), class_="exhibit")
        if view.phase != Phase.BRIEFING else None,
        ui.h3("Exhibits"),
        *(ui.tags.details(ui.tags.summary(item.title), ui.p(item.text), class_="exhibit") for item in view.exhibits),
        ui.h3("Witnesses") if view.witnesses else None,
        *(
            ui.tags.details(
                ui.tags.summary(person.name),
                ui.p(person.profile),
                ui.p("Your lineup" if person.id in view.player_lineup else "Rival lineup", class_="status-line")
                if person.id in view.player_lineup + view.rival_lineup else None,
                class_="exhibit",
            )
            for person in view.witnesses
        ),
        class_="panel case-file",
    )


def transcript(trial: Trial):
    return ui.tags.section(
        ui.h2("Trial record"),
        ui.tags.ol(*(
            ui.tags.li(
                ui.div(
                    ui.strong(f"#{entry.number} · {entry.speaker}"),
                    ui.span(entry.status.value, class_="record-status"),
                ),
                ui.p(entry.text),
                class_=f"record {entry.status.name.lower()}",
            )
            for entry in reversed(trial.record)
        ), class_="record-list"),
        ui.p("The record is empty.") if not trial.record else None,
        class_="panel transcript",
    )


def new_game() -> Game:
    seed = secrets.randbits(32)
    return Game(select_case(CASES, seed), seed)


def notice_view(status):
    if status is None:
        return None
    message, failed = status
    return ui.p(message, class_="notice error" if failed else "notice", role="alert" if failed else "status")


def connection_screen(mode: str, models: dict[str, str], waiting: bool, status):
    return ui.div(
        ui.h1("Choose how to play"),
        notice_view(status),
        ui.p("Checking the selected model…", role="status") if waiting else ui.div(
            ui.input_radio_buttons(
                "model_mode", "Witness dialogue",
                {"practice": "Scripted practice", "ollama": "Ollama", "openai": "OpenAI"},
                selected=mode,
            ),
            ui.panel_conditional(
                "input.model_mode === 'ollama'",
                ui.input_text("ollama_model", "Installed Ollama model", value=models["ollama"]),
                ui.p("Uses the Ollama server configured for this Shiny app."),
            ),
            ui.panel_conditional(
                "input.model_mode === 'openai'",
                ui.input_text("openai_model", "OpenAI model", value=models["openai"]),
                ui.input_password("api_token", "OpenAI API token"),
                ui.p("The server keeps your token for this session. Model calls may use your API credits."),
            ),
            ui.input_action_button("connect_model", "Continue to case", class_="btn-primary"),
        ),
        class_="panel model-setup",
    )


def server(input: Inputs, output: Outputs, session: Session):
    game = new_game()
    trial: Trial | None = None
    verdict: Verdict | None = None
    sentence_result: SentenceResult | None = None
    revision = reactive.Value(0)
    notice = reactive.Value(None)
    dialogue: Dialogue | None = None
    active_label = "Model setup"
    mode = "practice"
    models = {"ollama": DEFAULT_OLLAMA_MODEL, "openai": DEFAULT_HOSTED_MODEL}
    in_flight: int | None = None
    sequence = 0
    pending_connection: tuple[Dialogue, str] | None = None
    pending_question: tuple[Trial, QuestionRequest] | None = None
    draft_question = ""

    @reactive.extended_task
    async def model_call(ticket, work):
        try:
            return ticket, await asyncio.to_thread(work), None
        except ModelError as error:
            return ticket, None, str(error)

    def submit(work):
        nonlocal sequence, in_flight
        sequence += 1
        in_flight = sequence
        model_call.invoke(sequence, work)

    @reactive.effect
    @reactive.event(model_call.result)
    def model_finished():
        nonlocal in_flight, pending_connection, pending_question, dialogue, active_label, draft_question
        ticket, result, error = model_call.result()
        if ticket != in_flight:
            return
        connecting, asking = pending_connection, pending_question
        pending_connection, pending_question, in_flight = None, None, None
        if error:
            notice.set((error, True))
        elif connecting:
            dialogue, active_label = connecting
        elif asking and trial is asking[0]:
            try:
                trial.apply_question(asking[1], result)
            except GameError as rejected:
                notice.set((str(rejected), True))
            else:
                draft_question = ""
        revision.set(revision.get() + 1)

    def bind(button, action):
        @reactive.effect
        @reactive.event(input[button])
        def on_action():
            if in_flight is not None:
                return
            try:
                message = action()
            except GameError as error:
                notice.set((str(error), True))
            else:
                notice.set((message, False) if message else None)
            revision.set(revision.get() + 1)

    def connect_model():
        nonlocal dialogue, active_label, mode, pending_connection
        if dialogue is not None:
            return
        mode = input.model_mode()
        if mode == "practice":
            dialogue, active_label = ScriptedDialogue(), "Scripted practice"
            return
        if mode == "ollama":
            models[mode] = (input.ollama_model() or "").strip()
            adapter = OllamaDialogue(
                models[mode], os.environ.get("SHINY_OBJECTION_OLLAMA_URL", DEFAULT_OLLAMA_URL),
            )
            label = f"Ollama · {adapter.model}"
        elif mode == "openai":
            models[mode] = (input.openai_model() or "").strip()
            token = input.api_token() or ""
            ui.update_text("api_token", value="", session=session)
            adapter = OpenAIDialogue(token, models[mode])
            label = f"OpenAI · {adapter.model}"
        else:
            raise GameError("Choose a supported dialogue mode.")
        pending_connection = adapter, label
        submit(lambda: verify_connection(adapter))

    def change_model():
        nonlocal dialogue, active_label
        if game.phase != Phase.BRIEFING:
            raise GameError("Change the model from the police briefing before choosing a side.")
        dialogue, active_label = None, "Model setup"

    def investigate():
        return f"Investigated {game.investigate(input.lead() or '')}."

    def start_trial():
        nonlocal trial
        if dialogue is None:
            raise GameError("Choose a dialogue mode before starting the trial.")
        game.choose_witnesses(tuple(input.witnesses() or ()))
        trial = Trial(game, dialogue)

    def require_trial() -> Trial:
        if trial is None:
            raise GameError("Start the trial first.")
        return trial

    def ask():
        nonlocal pending_question, draft_question
        active = require_trial()
        draft_question = input.question() or ""
        if mode == "practice":
            active.ask(draft_question)
            draft_question = ""
            return
        request = active.prepare_question(draft_question)
        pending_question = active, request
        adapter = active.dialogue
        submit(lambda: adapter.interpret(request.question, request.eligible, request.context))

    def hear_verdict():
        nonlocal verdict
        active = require_trial()
        try:
            citations = tuple(int(value) for value in input.citations() or ())
        except ValueError as error:
            raise GameError("Select citations from the admitted record.") from error
        verdict = deliberate(active, input.closing_text() or "", citations)

    def hear_sentence():
        nonlocal sentence_result
        active = require_trial()
        if verdict is None or verdict.sentencing is None:
            raise GameError("Hear the verdict before sentencing.")
        factors = verdict.sentencing.factors
        if active.side == Side.PROSECUTION:
            requested = tuple(factor.label for factor in factors)
        else:
            requested = tuple(input.mitigation() or ()) if factors else ()
        sentence_result = sentence(verdict, requested)

    def restart():
        nonlocal game, trial, verdict, sentence_result, draft_question
        game, trial, verdict, sentence_result = new_game(), None, None, None
        draft_question = ""

    def clear_model():
        nonlocal dialogue, trial, pending_connection, pending_question, in_flight
        model_call.cancel()
        dialogue, trial, pending_connection, pending_question, in_flight = None, None, None, None, None

    session.on_ended(clear_model)

    bind("connect_model", connect_model)
    bind("change_model", change_model)
    bind("prosecution", lambda: game.choose_side(Side.PROSECUTION))
    bind("defense", lambda: game.choose_side(Side.DEFENSE))
    bind("investigate", investigate)
    bind("finish_investigation", lambda: game.finish_investigation())
    bind("start_trial", start_trial)
    bind("ask", ask)
    bind("offer", lambda: require_trial().offer(input.exhibit() or ""))
    bind("end_exam", lambda: require_trial().end_examination())
    bind("rival_next", lambda: require_trial().rival_next())
    bind("pass_move", lambda: require_trial().pass_rival_move())
    bind("object", lambda: require_trial().object(Ground(input.ground()), input.objection_reason() or ""))
    bind("reply", lambda: require_trial().reply(input.reply_text() or ""))
    bind("deliberate", hear_verdict)
    bind("sentence", hear_sentence)
    bind("restart", restart)

    @render.text
    def active_mode():
        revision.get()
        return active_label

    @render.ui
    def play():
        revision.get()
        status = notice.get()
        if dialogue is None:
            return connection_screen(mode, models, in_flight is not None, status)
        view = game.view()
        if verdict is not None and trial is not None:
            pane = verdict_view(trial, verdict, sentence_result)
        elif trial is not None:
            pane = courtroom(view, trial, in_flight is not None, draft_question) if trial.turn else closing(trial)
        elif view.phase == Phase.WITNESS_SELECTION:
            pane = choose_witnesses(view)
        elif view.phase == Phase.INVESTIGATION:
            pane = investigation(view)
        else:
            pane = ui.div(
                briefing(view),
                ui.input_action_button("change_model", "Change dialogue mode", class_="btn-outline-primary"),
            )

        return ui.div(
            ui.div(
                ui.p(view.jurisdiction, class_="status-line"),
                ui.h1(view.title),
                ui.p(view.charge, class_="charge"),
                ui.p(f"Your side: {view.side.value.title()}", class_="side") if view.side else None,
                class_="case-heading",
            ),
            ui.div(
                ui.div(
                    ui.tags.section(
                        notice_view(status),
                        pane,
                        class_="panel stage",
                    ),
                    transcript(trial) if trial is not None else None,
                    class_="hearing",
                ),
                case_file(view),
                class_="layout",
            ),
        )


app = App(
    ui.page_fluid(
        ui.tags.link(rel="stylesheet", href="courtroom.css"),
        ui.tags.header(
            ui.tags.img(src="logo.svg", alt="", width="40", height="40"),
            ui.span("Shiny Objection", class_="wordmark"),
            ui.span(ui.output_text("active_mode", inline=True), class_="practice"),
            class_="masthead",
        ),
        ui.tags.main(ui.output_ui("play"), class_="room"),
        title="Shiny Objection",
    ),
    server,
    static_assets=ROOT / "static",
)
