from pathlib import Path
import re


def test_services_do_not_access_dependency_private_attributes() -> None:
    """
    Service classes can use their own private helpers/state (`self._...`), but
    should not read/write private fields on injected dependencies.
    """
    service_root = Path("services")
    patterns = [
        re.compile(r"\bself\.[A-Za-z]\w*_(?:manager|service|store)\._[A-Za-z]\w*"),
        re.compile(
            r'getattr\(\s*self\.[A-Za-z]\w*_(?:manager|service|store)\s*,\s*"_'
        ),
    ]
    offenders = []

    for py_file in service_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        for line_no, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in patterns):
                offenders.append(f"{py_file}:{line_no}: {line.strip()}")

    assert not offenders, (
        "Service dependency private-attribute access found:\n" + "\n".join(offenders)
    )
