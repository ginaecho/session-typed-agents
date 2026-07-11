"""Payload sanitizer — plan v2.1 §5.2.

Judges must receive ONLY their class-specific view of a validated global
protocol G: no comments, no case names, no file paths, no provenance, no
drafting/repair traces, no whitespace fingerprints that could leak anything
beyond the protocol's own semantics.

The mechanism (why this is not "regex comment stripping" masquerading as
something safer): comments are stripped from the source text *before* any
parsing happens (``_strip_comments``), and the canonical output is then
built by walking the recursive AST that
``stjp_core.critic.protocol_paths.parse_global_ast`` produces (GSeq of
``GMessage`` / ``GChoice`` / ``("__rec__", ...)`` nodes) and re-emitting each
node from a fixed template. No substring of the original raw source ever
reaches the output except the small regex-captured identifier/type tokens
that the AST parser itself extracts (role names, message labels, sender,
receiver, payload-type text) — and those are extracted from the
*already-comment-stripped* text, so a comment's contents can never survive
into a captured field either. A prompt-injection payload hidden in a
comment has no path into the sanitized text: it is deleted before the
parser ever sees it, and the parser has no "free text" field into which
deleted content could be resurrected.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from stjp_core.critic.protocol_paths import (
    GChoice,
    GMessage,
    ProtocolPathError,
    parse_global_ast,
)

_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

_GLOBAL_HEADER_RE = re.compile(
    r"(aux\s+)?global\s+protocol\s+(\w+)\s*\(([^)]*)\)\s*\{", re.DOTALL
)
_MODULE_RE = re.compile(r"module\s+(\w+)\s*;")
_ROLE_RE = re.compile(r"\brole\s+(\w+)")


class PayloadSanitizationError(Exception):
    """Raised when a protocol source cannot be safely sanitized."""


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments. Must run before ANY field extraction.

    Non-nested block comments only (matches Scribble/Java lexical
    convention, and matches ``protocol_paths._strip_comments``): a
    malformed "nested" block comment leaves a stray ``*/`` and whatever
    text sat between the inner and outer close markers as ordinary text,
    which then either has to be valid Scribble syntax (and therefore
    carries no injected prose) or causes the downstream AST parse to fail
    loudly — it is never silently absorbed into the sanitized output.
    """
    text = _LINE_COMMENT_RE.sub("", text)
    text = _BLOCK_COMMENT_RE.sub("", text)
    return text


def _header_fields(stripped: str, protocol_name: str | None) -> tuple[str, str, list[str]]:
    """Extract (module_name, protocol_name, roles) from COMMENT-STRIPPED text.

    Deliberately reimplemented here rather than reusing
    ``stjp_core.compiler.protocol_parser`` — that module's regexes run
    against raw (comment-bearing) source, so a comment sitting inside the
    role-declaration parens of ``global protocol Foo(role A, /* ... */
    role B)`` would leak through its ``_extract_roles``. Running the same
    shape of regex against pre-stripped text closes that hole.
    """
    module_match = _MODULE_RE.search(stripped)
    module_name = module_match.group(1) if module_match else ""

    blocks = list(_GLOBAL_HEADER_RE.finditer(stripped))
    if not blocks:
        raise PayloadSanitizationError("no global protocol block found")

    if protocol_name is None:
        aux_names = {m.group(2) for m in blocks if m.group(1)}
        candidates = [m for m in blocks if m.group(2) not in aux_names] or blocks
        chosen = candidates[0]
    else:
        matches = [m for m in blocks if m.group(2) == protocol_name]
        if not matches:
            raise PayloadSanitizationError(f"protocol {protocol_name!r} not found")
        chosen = matches[0]

    roles = _ROLE_RE.findall(chosen.group(3))
    return module_name, chosen.group(2), roles


def _render_seq(seq: list, indent: int) -> list[str]:
    pad = "    " * indent
    lines: list[str] = []
    for node in seq:
        if isinstance(node, GMessage):
            lines.append(f"{pad}{node.label}({node.payload}) from {node.sender} to {node.receiver};")
        elif isinstance(node, GChoice):
            lines.append(f"{pad}choice at {node.role} {{")
            for i, branch in enumerate(node.branches):
                if i > 0:
                    lines.append(f"{pad}}} or {{")
                lines.extend(_render_seq(branch, indent + 1))
            lines.append(f"{pad}}}")
        elif isinstance(node, tuple) and node[0] == "__rec__":
            # Recursion is unrolled once by parse_global_ast; render the
            # unrolled body — no raw source text passes through here either.
            lines.extend(_render_seq(node[1], indent))
        else:  # pragma: no cover - defensive; AST only emits the above
            raise PayloadSanitizationError(f"unrecognised AST node: {node!r}")
    return lines


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class SanitizedPayload:
    """The comment-free, whitespace-normalized, provenance-free view of G
    that judges are allowed to see. Nothing else about the case (case
    name, file path, drafting trace, validator log) is carried on this
    object by construction — callers must not staple it back on."""

    text: str
    module_name: str
    protocol_name: str
    roles: list[str]
    message_labels: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    payload_hash: str = ""

    def __post_init__(self) -> None:
        if not self.payload_hash:
            self.payload_hash = hash_text(self.text)


def sanitize_protocol(source_text: str, protocol_name: str | None = None) -> SanitizedPayload:
    """Parse + re-emit ``source_text`` as a canonical, comment-free payload.

    Raises ``PayloadSanitizationError`` on anything that doesn't parse as a
    well-formed global-protocol body — malformed input is rejected, never
    partially emitted.
    """
    stripped = _strip_comments(source_text)
    module_name, resolved_name, roles = _header_fields(stripped, protocol_name)

    notes: list[str] = []
    try:
        ast = parse_global_ast(stripped, resolved_name, _notes=notes)
    except ProtocolPathError as exc:
        raise PayloadSanitizationError(str(exc)) from exc

    body_lines = _render_seq(ast, indent=1)
    role_decl = ", ".join(f"role {r}" for r in roles)
    header = f"module {module_name};\n\nglobal protocol {resolved_name}({role_decl}) {{"
    text = header + "\n" + "\n".join(body_lines) + "\n}\n"

    message_labels = sorted({node.label for node in _flatten(ast)})

    return SanitizedPayload(
        text=text,
        module_name=module_name,
        protocol_name=resolved_name,
        roles=roles,
        message_labels=message_labels,
        notes=notes,
    )


def _flatten(seq: list):
    for node in seq:
        if isinstance(node, GMessage):
            yield node
        elif isinstance(node, GChoice):
            for branch in node.branches:
                yield from _flatten(branch)
        elif isinstance(node, tuple) and node[0] == "__rec__":
            yield from _flatten(node[1])
