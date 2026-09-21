"""Text templates for prompts and copy. Placeholders are plain names only (`{fields}`): no attribute or
index access, no format spec, no conversion. A bundle may be edited outside the codebase (S3), so a
template must never reach into the objects it is rendered with. `{{` and `}}` are literal braces."""

from __future__ import annotations

import string
from typing import Any

_FORMATTER = string.Formatter()


class ConfigError(ValueError):
    """The agent config bundle cannot be used. `problems` lists every issue found, not just the first."""

    def __init__(self, problems: list[str] | str) -> None:
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("invalid agent config:\n" + "\n".join(f"- {p}" for p in self.problems))


class Template:
    __slots__ = ("fields", "text")

    def __init__(self, text: str, where: str) -> None:
        if not isinstance(text, str):
            raise ConfigError(f"{where}: expected text, got {type(text).__name__}")
        try:
            parsed = list(_FORMATTER.parse(text))
        except ValueError as exc:
            raise ConfigError(f"{where}: {exc} (write a literal brace as {{{{ or }}}})") from None
        fields: set[str] = set()
        for _literal, name, spec, conversion in parsed:
            if name is None:
                continue
            if not name.isidentifier():
                raise ConfigError(f"{where}: placeholder {{{name}}} must be a plain name")
            if spec or conversion:
                raise ConfigError(f"{where}: placeholder {{{name}}} may not have a format spec or conversion")
            fields.add(name)
        self.text = text
        self.fields = frozenset(fields)

    def render(self, **values: Any) -> str:
        missing = self.fields - values.keys()
        if missing:
            raise KeyError(f"template needs {sorted(missing)}")
        return _FORMATTER.vformat(self.text, (), values)

    def __repr__(self) -> str:
        return f"Template({self.text!r})"
