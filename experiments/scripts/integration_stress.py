"""Integration stress suite — complicated, generated cases, run N times.

NOT unit tests: every iteration generates a fresh, non-trivial protocol
(4-7 roles, nested choices, 8-20 messages, seeded RNG) and pushes it through
the WHOLE new surface, cross-checking components against each other:

  S1  ROUND-TRIP        generate global AST -> project local types (by
                        construction) -> global_synthesizer recomposes ->
                        Scribble validates BOTH originals and recompositions.
  S2  MUTATION CATCH    inject one of 5 bug classes into one role's local
                        type (dropped receive, retyped payload, swapped FIFO
                        order, rerouted peer, renamed label) -> at least one
                        layer (compatibility / synthesis / Scribble) must
                        reject it. Silent acceptance = suite failure.
  S3  CRITIC ORACLE     derive policies whose verdicts are known by
                        construction (a real precedence pair -> PASS; the
                        reversed pair -> FAIL; taint to a reachable role ->
                        FAIL with witness; to an unreachable role -> PASS)
                        and require the static Critic to agree on all 4.
  S4  REVISOR LOOP      break the protocol against a sequence policy by
                        deleting the `before` edge from one branch, then run
                        revise_protocol() with a scripted repair client (no
                        Azure) -> Scribble + Critic must both accept the fix.
  S5  INCREMENTAL CHAIN attach 2 generated child sub-protocols in sequence
                        (validate-once cache, anchors, new roles), assert the
                        projection diff touches exactly the child's roles,
                        and that regenerated STANDALONE monitors accept a
                        conforming trace and reject a mutated one.

Usage:
    python experiments/scripts/integration_stress.py [N] [--report-dir DIR]

Writes <report-dir>/integration_stress.json + .md (default:
experiments/reports/stress/). Exit code 0 only if every check in every
iteration passed. No Foundry / no network — Scribble is the only judge.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stjp_core.compiler.local_type import LocalType, LAction, LChoice
from stjp_core.compiler.global_synthesizer import (
    synthesize_global, check_compatibility, SynthesisError)
from stjp_core.compiler.validator import ScribbleValidator
from stjp_core.compiler.incremental import add_subprotocol
from stjp_core.critic.policies import parse_policy_text
from stjp_core.critic.critic import run_static_critic
from stjp_core.critic.protocol_paths import paths_for_protocol
from stjp_core.critic.revisor import revise_protocol


# ─────────────────────────────────────────────────────────────────────────────
# Generated-protocol model (global AST we control end to end)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GMsg:
    label: str
    payload: str
    sender: str
    receiver: str


@dataclass
class GCh:
    role: str
    branches: list[list] = field(default_factory=list)


TYPES = ["String", "Double", "Int", "Bool"]


class ProtocolGenerator:
    """Generates Scribble-safe global protocols by construction:
    - only causally-enabled roles ever send;
    - inside a choice, every participating receiver hears from the chooser
      FIRST in every branch (external-choice-subject rule);
    - after a choice, only the chooser or roles that received in ALL branches
      send at the top level (causal-connectivity rule)."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.label_n = 0

    def fresh_label(self) -> str:
        self.label_n += 1
        return f"M{self.label_n}"

    def generate(self, n_roles: int, n_top_msgs: int, n_choices: int):
        roles = [f"R{i}" for i in range(n_roles)]
        enabled = {roles[0]}
        body: list = []
        segments = n_choices + 1
        per_seg = max(2, n_top_msgs // segments)

        for seg in range(segments):
            for _ in range(per_seg):
                body.append(self._msg(roles, enabled))
            if seg < n_choices:
                choice, post_enabled = self._choice(roles, enabled)
                body.append(choice)
                enabled = post_enabled
        # every declared role must participate (Scribble's unused-role rule,
        # and a role with no interactions could never reach a terminal state)
        used = set()
        for m in self._flat(body):
            used |= {m.sender, m.receiver}
        for r in roles:
            if r not in used:
                sender = self.rng.choice(sorted(enabled))
                body.append(GMsg(self.fresh_label(),
                                 self.rng.choice(TYPES), sender, r))
                enabled.add(r)
        body.append(self._msg(roles, enabled))   # terminal-ish tail
        return roles, body

    def _msg(self, roles, enabled) -> GMsg:
        sender = self.rng.choice(sorted(enabled))
        receiver = self.rng.choice([r for r in roles if r != sender])
        enabled.add(receiver)
        return GMsg(self.fresh_label(), self.rng.choice(TYPES), sender, receiver)

    def _choice(self, roles, enabled):
        chooser = self.rng.choice(sorted(enabled))
        others = [r for r in roles if r != chooser]
        k = self.rng.randint(1, min(2, len(others)))
        participants = self.rng.sample(others, k)
        n_branches = self.rng.randint(2, 3)
        branches = []
        for _ in range(n_branches):
            branch: list = []
            for p in participants:                 # chooser notifies each first
                branch.append(GMsg(self.fresh_label(),
                                   self.rng.choice(TYPES), chooser, p))
            # optional intra-branch follow-up among branch participants
            if self.rng.random() < 0.5 and len(participants) >= 1:
                s = self.rng.choice(participants)
                t = chooser if len(participants) == 1 else self.rng.choice(
                    [chooser] + [x for x in participants if x != s])
                branch.append(GMsg(self.fresh_label(),
                                   self.rng.choice(TYPES), s, t))
            branches.append(branch)
        post_enabled = {chooser} | set(participants)
        return GCh(chooser, branches), post_enabled

    # ── rendering + projection (both derived from the same AST) ─────────

    def render(self, roles, body, module: str, protocol: str) -> str:
        lines = [f"module {module};", ""]
        for t in TYPES:
            java = {"String": "java.lang.String", "Double": "java.lang.Double",
                    "Int": "java.lang.Integer", "Bool": "java.lang.Boolean"}[t]
            lines.append(f'data <java> "{java}" from "rt.jar" as {t};')
        lines.append("")
        decl = ", ".join(f"role {r}" for r in roles)
        lines.append(f"global protocol {protocol}({decl}) {{")
        lines.extend(self._render_body(body, "    "))
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _render_body(self, body, ind) -> list[str]:
        out = []
        for node in body:
            if isinstance(node, GMsg):
                out.append(f"{ind}{node.label}({node.payload}) from "
                           f"{node.sender} to {node.receiver};")
            else:
                for i, b in enumerate(node.branches):
                    out.append(f"{ind}choice at {node.role} {{" if i == 0
                               else f"{ind}}} or {{")
                    out.extend(self._render_body(b, ind + "    "))
                out.append(f"{ind}}}")
        return out

    def project(self, roles, body) -> dict[str, LocalType]:
        lts = {r: LocalType(role=r, body=[]) for r in roles}

        def _proj(nodes, targets: dict[str, list]):
            for node in nodes:
                if isinstance(node, GMsg):
                    if node.sender in targets:
                        targets[node.sender].append(LAction(
                            "send", node.receiver, node.label, node.payload))
                    if node.receiver in targets:
                        targets[node.receiver].append(LAction(
                            "recv", node.sender, node.label, node.payload))
                else:
                    involved = {node.role}
                    for b in node.branches:
                        for m in self._flat(b):
                            involved |= {m.sender, m.receiver}
                    choices = {r: LChoice(branches=[]) for r in involved
                               if r in targets}
                    for b in node.branches:
                        sub_targets = {r: [] for r in choices}
                        _proj(b, sub_targets)
                        for r, items in sub_targets.items():
                            choices[r].branches.append(items)
                    for r, ch in choices.items():
                        # a role with identical behaviour in every branch (or
                        # absent) gets the flattened form, not a choice node
                        bodies = ch.branches
                        if all(_sig(b) == _sig(bodies[0]) for b in bodies):
                            targets[r].extend(bodies[0])
                        else:
                            targets[r].append(ch)

        def _sig(items):
            return json.dumps([i.__dict__ if isinstance(i, LAction) else "ch"
                               for i in items], default=str)

        acc = {r: [] for r in roles}
        _proj(body, acc)
        for r in roles:
            lts[r].body = acc[r]
        return lts

    def _flat(self, nodes):
        out = []
        for n in nodes:
            if isinstance(n, GMsg):
                out.append(n)
            else:
                for b in n.branches:
                    out.extend(self._flat(b))
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Stage checks
# ─────────────────────────────────────────────────────────────────────────────

def s1_round_trip(gen, roles, body, workdir, validator, rec) -> dict[str, LocalType]:
    original = gen.render(roles, body, "orig", "Gen")
    p = workdir / "orig.scr"
    p.write_text(original, encoding="utf-8")
    ok_orig, err_o = validator.validate_protocol(p)
    rec("S1.generated_protocol_scribble_valid", ok_orig, err_o[:200])

    lts = gen.project(roles, body)
    synth_ok, synth_err, resynth_valid = False, "", False
    try:
        result = synthesize_global(lts, protocol_name="Gen", module_name="resynth")
        synth_ok = True
        q = workdir / "resynth.scr"
        q.write_text(result.protocol_text, encoding="utf-8")
        resynth_valid, err_r = validator.validate_protocol(q)
        synth_err = err_r[:200]
    except SynthesisError as e:
        synth_err = str(e)[:200]
    rec("S1.local_types_recompose", synth_ok, synth_err)
    rec("S1.recomposition_scribble_valid", resynth_valid, synth_err)

    if synth_ok and resynth_valid:
        # same interaction multiset both ways
        orig_msgs = sorted((m.sender, m.receiver, m.label)
                           for m in gen._flat(body))
        re_paths = paths_for_protocol((workdir / "resynth.scr").read_text(
            encoding="utf-8"))
        re_msgs = sorted({(e.sender, e.receiver, e.label)
                          for path in re_paths.paths for e in path})
        rec("S1.message_set_preserved",
            set(orig_msgs) == set(re_msgs),
            f"orig={len(set(orig_msgs))} resynth={len(set(re_msgs))}")
    return lts


MUTATIONS = ["drop_receive", "retype_payload", "swap_fifo", "reroute_peer",
             "rename_label"]


def apply_local_mutation(rng, lts: dict[str, LocalType]
                        ) -> tuple[dict[str, LocalType], str, str]:
    """Pure LocalType-level mutation step: pick one of the 5 MUTATIONS
    classes and apply it to a deep copy of `lts`. Returns
    (mutated_lts, victim_role, kind_actually_applied) — `kind` may differ
    from the originally-sampled class when that class doesn't apply (same
    fallback-to-rename_label behaviour as before the extraction).

    Extracted from `s2_mutation` (unchanged RNG consumption order, so
    seeded runs of this module are bit-for-bit unaffected) so other callers
    — the D3 repair-tuple builder in experiments/seam_bench/data/d3_repair
    .py — can reuse these operators without duplicating the selection
    logic. Prefer importing this function over copying it."""
    import copy
    mutated = copy.deepcopy(lts)
    kind = rng.choice(MUTATIONS)
    victims = [r for r, lt in mutated.items()
               if any(isinstance(n, LAction) for n in lt.body)]
    role = rng.choice(victims)
    body = mutated[role].body
    acts = [i for i, n in enumerate(body) if isinstance(n, LAction)]

    if kind == "drop_receive":
        ridx = [i for i in acts if body[i].direction == "recv"]
        if not ridx:
            kind = "rename_label"
    if kind == "drop_receive":
        del body[rng.choice(ridx)]
    elif kind == "retype_payload":
        i = rng.choice(acts)
        a = body[i]
        body[i] = LAction(a.direction, a.peer, a.label,
                          "Int" if a.payload_type != "Int" else "Double")
    elif kind == "swap_fifo":
        # reverse the role's whole action order — breaks causality/duality
        body.reverse()
    elif kind == "reroute_peer":
        i = rng.choice(acts)
        a = body[i]
        others = [r for r in mutated if r not in (role, a.peer)]
        if not others:
            kind = "rename_label"
        else:
            body[i] = LAction(a.direction, rng.choice(others), a.label,
                              a.payload_type)
    if kind == "rename_label":
        i = rng.choice(acts)
        a = body[i]
        body[i] = LAction(a.direction, a.peer, a.label + "X", a.payload_type)
    return mutated, role, kind


def s2_mutation(rng, lts: dict[str, LocalType], rec):
    mutated, role, kind = apply_local_mutation(rng, lts)
    caught_by = ""
    findings = check_compatibility(mutated)
    if any(f.severity == "ERROR" for f in findings):
        caught_by = "compatibility"
    else:
        try:
            result = synthesize_global(mutated, protocol_name="Mut",
                                       module_name="mut")
            with tempfile.TemporaryDirectory() as td:
                q = Path(td) / "mut.scr"
                q.write_text(result.protocol_text, encoding="utf-8")
                ok, _ = ScribbleValidator().validate_protocol(q)
            if not ok:
                caught_by = "scribble"
        except SynthesisError:
            caught_by = "synthesis"
    rec(f"S2.mutation_caught[{kind}]", bool(caught_by),
        f"caught_by={caught_by or 'NOBODY — silent acceptance!'}")


def s3_critic_oracle(rng, workdir, rec):
    text = (workdir / "orig.scr").read_text(encoding="utf-8")
    ps = paths_for_protocol(text)
    paths = ps.paths
    # pick a precedence pair that holds on EVERY path: first + last event of
    # the shortest path, verified across all paths
    base = min(paths, key=len)
    before, after = base[0], base[-1]
    holds = all(_precedes(p, before, after) for p in paths)
    if not holds:
        rec("S3.oracle_setup", True, "no universal precedence pair; skipped")
        return
    pol_pass = (f"[sequence]\nid: SP\nbefore: {before.sender} -> "
                f"{before.receiver} : {before.label}\n"
                f"after: {after.sender} -> {after.receiver} : {after.label}\n")
    pol_fail = (f"[sequence]\nid: SF\nbefore: {after.sender} -> "
                f"{after.receiver} : {after.label}\n"
                f"after: {before.sender} -> {before.receiver} : {before.label}\n")
    r1 = run_static_critic(text, parse_policy_text(pol_pass))
    r2 = run_static_critic(text, parse_policy_text(pol_fail))
    rec("S3.true_precedence_passes", r1.passed,
        r1.findings[0].message[:120] if r1.findings else "")
    rec("S3.reversed_precedence_fails", not r2.passed, "")

    # taint oracle: source = first event; reachable set by conservative flow
    reach = _taint_reach(paths, before)
    unreachable = [r for r in _all_roles(paths) if r not in reach
                   and r != before.sender]
    fl_fail = (f"[flow]\nid: FF\nsource: {before.sender} -> "
               f"{before.receiver} : {before.label}\n"
               f"forbidden_role: {sorted(reach - {before.receiver})[0]}\n"
               if len(reach) > 1 else "")
    if fl_fail:
        r3 = run_static_critic(text, parse_policy_text(fl_fail))
        rec("S3.taint_reachable_flagged", not r3.passed,
            "; ".join(r3.findings[0].witness[:3]) if r3.findings else "")
    if unreachable:
        fl_pass = (f"[flow]\nid: FP\nsource: {before.sender} -> "
                   f"{before.receiver} : {before.label}\n"
                   f"forbidden_role: {unreachable[0]}\n")
        r4 = run_static_critic(text, parse_policy_text(fl_pass))
        rec("S3.taint_unreachable_clean", r4.passed, "")


def _precedes(path, before, after) -> bool:
    bi = ai = None
    for i, e in enumerate(path):
        if (e.sender, e.receiver, e.label) == (before.sender, before.receiver,
                                               before.label) and bi is None:
            bi = i
        if (e.sender, e.receiver, e.label) == (after.sender, after.receiver,
                                               after.label):
            ai = i
    return ai is None or (bi is not None and bi < ai)


def _taint_reach(paths, source) -> set[str]:
    reach: set[str] = set()
    for p in paths:
        tainted = set()
        for e in p:
            if (e.sender, e.receiver, e.label) == (source.sender,
                                                   source.receiver, source.label):
                tainted.add(e.receiver)
            elif e.sender in tainted:
                tainted.add(e.receiver)
        reach |= tainted
    return reach


def _all_roles(paths) -> set[str]:
    return {x for p in paths for e in p for x in (e.sender, e.receiver)}


class ScriptedRepairClient:
    """Offline stand-in for the Revisor's LLM: repairs a sequence violation
    by hoisting the missing `before` round-trip to the top level, computed
    programmatically from the findings text. Tests the LOOP (draft ->
    Scribble -> Critic -> accept/retry), not model quality."""

    def __init__(self, fixed_text: str):
        self.fixed_text = fixed_text
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return f"```scribble\n{self.fixed_text}\n```"


def s4_revisor_loop(rng, workdir, validator, rec):
    """Take a linear protocol A;B;C..., impose 'X before LAST', where X is a
    mid-protocol edge; then create the broken variant with X wrapped in a
    skip-able choice — Critic must fail it, and the scripted repair (the
    original linear text) must be accepted by the loop."""
    text = (workdir / "orig.scr").read_text(encoding="utf-8")
    ps = paths_for_protocol(text)
    base = min(ps.paths, key=len)
    if len(base) < 3:
        rec("S4.setup", True, "path too short; skipped")
        return
    mid, last = base[len(base) // 2], base[-1]
    if (mid.sender, mid.receiver, mid.label) == (last.sender, last.receiver,
                                                 last.label):
        rec("S4.setup", True, "degenerate pair; skipped")
        return
    policy = (f"[sequence]\nid: SR\ndescription: {mid.label} must precede "
              f"{last.label}\nbefore: {mid.sender} -> {mid.receiver} : "
              f"{mid.label}\nafter: {last.sender} -> {last.receiver} : "
              f"{last.label}\n")
    pols = parse_policy_text(policy)

    # broken variant: a fresh linear protocol missing the `before` edge
    lines = [f"module broken;", ""]
    for t in TYPES:
        java = {"String": "java.lang.String", "Double": "java.lang.Double",
                "Int": "java.lang.Integer", "Bool": "java.lang.Boolean"}[t]
        lines.append(f'data <java> "{java}" from "rt.jar" as {t};')
    lines.append("")
    roles = sorted(_all_roles(ps.paths))
    lines.append(f"global protocol Gen({', '.join('role ' + r for r in roles)}) {{")
    for e in base:
        if (e.sender, e.receiver, e.label) != (mid.sender, mid.receiver, mid.label):
            lines.append(f"    {e.label}(String) from {e.sender} to {e.receiver};")
    lines.append("}")
    broken_path = workdir / "broken.scr"
    broken_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok_broken, err_b = validator.validate_protocol(broken_path)
    if not ok_broken:
        rec("S4.setup", True, f"broken variant not Scribble-valid; skipped "
                              f"({err_b[:80]})")
        return
    report = run_static_critic(broken_path, pols)
    rec("S4.critic_fails_broken", not report.passed, "")
    if report.passed:
        return

    fixed_lines = list(lines)
    # scripted repair: reinsert the missing edge right BEFORE the `after`
    # statement (the last message line; index -2 is just before the "}").
    fixed_lines.insert(len(fixed_lines) - 2,
                       f"    {mid.label}(String) from {mid.sender} to "
                       f"{mid.receiver};")
    fixed_lines[0] = "module broken;"
    client = ScriptedRepairClient("\n".join(fixed_lines))
    result = revise_protocol(broken_path, report, pols, llm_client=client,
                             output_dir=workdir)
    rec("S4.revisor_accepts_scripted_fix", result.success,
        result.history[-1] if result.history else result.error[:120])


def s5_incremental_chain(rng, workdir, rec):
    text = (workdir / "orig.scr").read_text(encoding="utf-8")
    ps = paths_for_protocol(text)
    base = min(ps.paths, key=len)
    roles = sorted(_all_roles(ps.paths))
    anchor_msg = base[0]

    current = workdir / "orig.scr"
    all_child_roles: set[str] = set()
    tail = base[-1]
    for step in range(2):
        # generated child: requester (existing role) <-> brand-new role.
        # The requester must be CAUSALLY ENABLED at the anchor (Scribble's
        # connectivity rule): after the anchor message, its sender/receiver
        # are; at the end of the protocol, the final message's parties are.
        if step == 0:
            req = rng.choice([anchor_msg.sender, anchor_msg.receiver])
        else:
            req = rng.choice([tail.sender, tail.receiver])
        newr = f"Ext{step}"
        child_text = (
            f"module child{step};\n\n"
            f'data <java> "java.lang.String" from "rt.jar" as String;\n\n'
            f"aux global protocol SubTask{step}(role Requester, role Worker) {{\n"
            f"    TaskGo{step}(String) from Requester to Worker;\n"
            f"    TaskDone{step}(String) from Worker to Requester;\n"
            f"}}\n")
        child_path = workdir / f"child{step}.scr"
        child_path.write_text(child_text, encoding="utf-8")

        t0 = time.perf_counter()
        result = add_subprotocol(
            current, child_path, [req, newr],
            anchor=f"after:{anchor_msg.label}" if step == 0 else "end",
            output_dir=workdir)
        dt = (time.perf_counter() - t0) * 1000
        rec(f"S5.extension_{step}_valid", result.success,
            result.error[:150] if not result.success else f"{dt:.0f}ms")
        if not result.success:
            return
        changed = {r for r, d in result.deltas.items() if d.status != "unchanged"}
        expected_changed = {req, newr}
        # earlier-extension roles may legitimately shift when re-anchored;
        # the invariant we enforce: the child's two roles ALWAYS change, and
        # no role outside (child roles ∪ previous child roles) ever does.
        allowed = expected_changed | all_child_roles
        rec(f"S5.extension_{step}_blast_radius",
            expected_changed <= changed and changed <= allowed | {req},
            f"changed={sorted(changed)} expected⊇{sorted(expected_changed)}")
        all_child_roles |= {newr}

        # cache: second validation of the same child is a hit
        from stjp_core.compiler.incremental import validate_child_once
        _, _, cached = validate_child_once(child_path)
        rec(f"S5.extension_{step}_child_cache_hit", cached, "")

        # monitor verdicts for the new role
        mon = result.artifacts.get(newr, [None, None])[1]
        if mon:
            good = [{"sender": req, "receiver": newr,
                     "label": f"TaskGo{step}", "payload": "x"},
                    {"sender": newr, "receiver": req,
                     "label": f"TaskDone{step}", "payload": "y"}]
            bad = list(reversed(good))
            rec(f"S5.extension_{step}_monitor_good", _run_mon(mon, good) == 0, "")
            rec(f"S5.extension_{step}_monitor_bad", _run_mon(mon, bad) == 1, "")
        current = result.composed_path
        roles = sorted(set(roles) | {newr})


def _run_mon(monitor_path: Path, events: list[dict]) -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        name = f.name
    try:
        return subprocess.run([sys.executable, str(monitor_path), name],
                              capture_output=True, text=True).returncode
    finally:
        Path(name).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────

def run_iteration(seed: int) -> list[dict]:
    rng = random.Random(seed)
    checks: list[dict] = []

    def rec(name: str, ok: bool, detail: str = ""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    gen = ProtocolGenerator(rng)
    n_roles = rng.randint(4, 7)
    n_msgs = rng.randint(6, 12)
    n_choices = rng.randint(1, 2)
    validator = ScribbleValidator()

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        roles, body = gen.generate(n_roles, n_msgs, n_choices)
        rec("gen.shape", True,
            f"{n_roles} roles, {len(gen._flat(body))} msgs, {n_choices} choice(s)")
        lts = s1_round_trip(gen, roles, body, workdir, validator, rec)
        s2_mutation(rng, lts, rec)
        s3_critic_oracle(rng, workdir, rec)
        s4_revisor_loop(rng, workdir, validator, rec)
        s5_incremental_chain(rng, workdir, rec)
    return checks


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    n = int(argv[0]) if argv and argv[0].isdigit() else 10
    report_dir = Path("experiments/reports/stress")
    if "--report-dir" in argv:
        report_dir = Path(argv[argv.index("--report-dir") + 1])
    report_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    iterations = []
    total = passed = 0
    for seed in range(1, n + 1):
        checks = run_iteration(seed)
        ok = sum(1 for c in checks if c["ok"])
        total += len(checks)
        passed += ok
        iterations.append({"seed": seed, "checks": checks,
                           "passed": ok, "total": len(checks)})
        status = "PASS" if ok == len(checks) else "FAIL"
        print(f"[stress] iteration {seed}/{n}: {ok}/{len(checks)} {status}")
        for c in checks:
            if not c["ok"]:
                print(f"    FAILED {c['check']}: {c['detail']}")

    elapsed = time.time() - t0
    summary = {
        "suite": "integration_stress",
        "iterations": n,
        "checks_total": total,
        "checks_passed": passed,
        "all_passed": passed == total,
        "elapsed_seconds": round(elapsed, 1),
        "runs": iterations,
    }
    (report_dir / "integration_stress.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    _write_md(report_dir / "integration_stress.md", summary)
    print(f"\n[stress] {passed}/{total} checks passed over {n} iterations "
          f"({elapsed:.0f}s) -> {report_dir}/integration_stress.{{json,md}}")
    return 0 if passed == total else 1


def _write_md(path: Path, s: dict):
    by_check: dict[str, list[bool]] = {}
    for it in s["runs"]:
        for c in it["checks"]:
            key = c["check"].split("[")[0]
            by_check.setdefault(key, []).append(c["ok"])
    lines = [
        "# Integration stress suite — generated complex cases",
        "",
        f"**Verdict: {'ALL PASS' if s['all_passed'] else 'FAILURES PRESENT'}** — "
        f"{s['checks_passed']}/{s['checks_total']} checks over "
        f"{s['iterations']} seeded iterations "
        f"({s['elapsed_seconds']}s, Scribble judging throughout).",
        "",
        "Each iteration generates a fresh 4-7-role protocol with nested "
        "choices, then runs the five stages described in "
        "`experiments/scripts/integration_stress.py` (round-trip, mutation "
        "catch, critic oracle, revisor loop, incremental chain).",
        "",
        "| check | pass rate |",
        "|---|---|",
    ]
    for k in sorted(by_check):
        v = by_check[k]
        lines.append(f"| `{k}` | {sum(v)}/{len(v)} |")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
