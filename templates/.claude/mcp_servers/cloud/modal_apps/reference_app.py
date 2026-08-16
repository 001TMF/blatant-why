"""Reference Modal app template for a BY design tool (boltzgen shown).

Importable without a GPU or a deploy — `modal deploy reference_app.py`
publishes it. The `app`/`function`/`gpu`/`image` here mirror the CATALOGUE
row in ../server.py; clone this file per tool, swapping those four fields.

NOTE: do NOT `modal run`/`modal deploy` this from tests — importing it is
enough to validate the app graph, and running it would spend GPU credits.
"""
import modal

# ponytail: real deps per tool go in pip_install; stub name here.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("boltzgen")
)

app = modal.App("by-boltzgen", image=image)


@app.function(gpu="A100", timeout=7200)
def design(input_files: list[str] | None = None, parameters: dict | None = None) -> dict:
    """Run boltzgen inside the image and return a JSON-serialisable result.

    ponytail: stub body — a real impl shells out to the tool CLI against
    files staged on a modal.Volume and parses its output directory.
    """
    parameters = parameters or {}
    num_designs = parameters.get("num_designs", 100)
    return {"tool": "boltzgen", "num_designs": num_designs, "status": "stub"}


if __name__ == "__main__":
    # Import-only smoke check; never spawns the function (no GPU spend).
    assert app.name == "by-boltzgen"
    assert "design" in app.registered_functions
    print("PASS reference_app imports; app =", app.name)
