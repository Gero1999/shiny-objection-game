"""Shiny controls shared by the dialogue screens."""

from shiny import ui


def input_area(id_, label, limit, **kwargs):
    field = ui.input_text_area(id_, label, width="100%", **kwargs)
    for child in field.children:
        if getattr(child, "name", None) == "textarea":
            child.attrs["maxlength"] = str(limit)
    return field



def log(messages, speaker):
    return ui.div(*(
        ui.div(ui.p(ui.strong("You"), " · ", message),
               ui.p(ui.strong(speaker), " · ", reply), class_="pending-move")
        for message, reply in messages
    ))
