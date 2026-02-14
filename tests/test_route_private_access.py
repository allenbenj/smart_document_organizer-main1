from pathlib import Path


def test_routes_do_not_access_private_attributes() -> None:
    """
    Route modules should not reach into private object internals (`obj._field`).
    Keep routing thin and depend on public service/manager APIs.
    """
    route_root = Path("routes")
    offenders = []

    for py_file in route_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        for line_no, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if "._" in line and "__" not in line:
                offenders.append(f"{py_file}:{line_no}: {line.strip()}")

    assert not offenders, "Private attribute access found in routes:\n" + "\n".join(offenders)
