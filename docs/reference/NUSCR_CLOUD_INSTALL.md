# Installing and running the new Scribble (nuscr coinductive fork)

How to install the **latest Scribble** — the coinductive nuscr fork at
[phou/nuscr_coinduction](https://github.com/phou/nuscr_coinduction) (a
**private repository**: the link works only for accounts with access; for
everyone else it shows GitHub's 404 page — use your own fork, e.g.
`ginaecho/nuscr_coinduction`, as described in the CI-artifact route below),
branch `coinductive_projection` (HEAD `cc7c72e`) — and drive it as an STJP
compiler backend. Two routes are documented: the **Docker route** (the fork's own
recipe, for machines with normal egress) and the **CI-artifact route**
(verified 2026-07-06 inside the Claude Code cloud execution environment,
whose network policy blocks Docker Hub blobs, opam.ocaml.org, and
unscoped GitHub).

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Route A — Docker (normal egress; the fork's own recipe)](#route-a--docker-normal-egress-the-forks-own-recipe)
- [Route B — CI-built native binary (restricted networks / cloud sandboxes)](#route-b--ci-built-native-binary-restricted-networks--cloud-sandboxes)
- [Running the fork by hand](#running-the-fork-by-hand)
<!-- MENU:END -->

## Route A — Docker (normal egress; the fork's own recipe)

The latest commit of the fork ships a `Dockerfile`, but its `opam install`
fails without the protobuf depexts, so the repo carries a wrapper image at
[tools/nuscr/Dockerfile](../../tools/nuscr/Dockerfile):

```bash
# 1. vendor the fork (git-ignored, like scribble-java/)
git clone --branch coinductive_projection \
    https://github.com/phou/nuscr_coinduction.git nuscr-coinduction

# 2. build the wrapper image (adds m4, libgmp, protobuf, pkg-config)
docker build -t nuscr-coind:latest -f tools/nuscr/Dockerfile ./nuscr-coinduction

# 3. smoke test (a quick end-to-end check)
docker run --rm nuscr-coind --help
docker run --rm -v "$PWD/nuscr-coinduction:/work" nuscr-coind \
    check /work/examples/from-scribble-java/tutorial/AsyncAdder.nuscr
```

STJP then uses it with no further configuration
(`STJP_COMPILER_BACKEND=nuscr`; image name via `STJP_NUSCR_IMAGE`,
default `nuscr-coind:latest`).

## Route B — CI-built native binary (restricted networks / cloud sandboxes)

The Claude Code cloud environment cannot run Route A: Docker Hub blob
downloads (`production.cloudfront.docker.com`) return 403 through the egress
proxy, `opam.ocaml.org` is blocked, and GitHub access is scoped to the repos
attached to the session. The working recipe, verified end-to-end on
2026-07-06:

1. **Fork the compiler repos into the session-owner's account** (the proxy
   only allows same-owner repos to be added to a session):
   `phou/nuscr_coinduction` → `ginaecho/nuscr_coinduction` and
   `scribble/scribble-java` → `ginaecho/scribble-java`. Add both to the
   session (`add_repo`) and clone.

2. **Build nuscr on a GitHub Actions runner** (runners have full egress) with
   the workflow committed on the fork's `ci-build` branch —
   `.github/workflows/build-nuscr.yml`. It builds with OCaml **5.3**
   (5.2 fails: `ppx_sexp_conv >= v0.17` together with `ppxlib >= 0.36`
   force the `ppxlib_jane` path, which needs `ocaml >= 5.3`), installs the
   protobuf depexts, then **commits the Linux binary to the `ci-artifacts`
   branch** as `dist/nuscr-linux-x86_64`. Committing to a branch — rather
   than uploading a workflow artifact — matters: artifact downloads redirect
   to a storage host the proxy blocks, while `git fetch` of the branch rides
   the allowed git path.

3. **Fetch and install the binary** in the sandbox:

   ```bash
   cd /workspace/nuscr_coinduction
   git fetch origin ci-artifacts
   git show FETCH_HEAD:dist/nuscr-linux-x86_64 > /usr/local/bin/nuscr
   chmod +x /usr/local/bin/nuscr
   nuscr --help   # ELF binary, runs natively on the Ubuntu 24.04 host
   ```

4. **Point STJP at the binary** — no Docker needed:

   ```bash
   export STJP_COMPILER_BACKEND=nuscr
   export STJP_NUSCR_BIN=/usr/local/bin/nuscr
   python stjp_core/tests/test_nuscr_backend.py   # ALL PASS incl. runtime tests
   ```

   `stjp_core/compiler/nuscr_compiler.py` runs the binary directly whenever
   `STJP_NUSCR_BIN` is set and falls back to `docker run` otherwise.

The same trick installs the **default Scribble backend** in the sandbox:
`scribble-java` master builds cleanly with the pre-installed Maven 3.9 +
JDK 21 (`mvn -DskipTests package`, deps come from Maven Central, which the
proxy allows); unzip `scribble-dist/target/scribble-dist-*.zip` into
`scribble-java/scribble-dist/target/` so `lib/*.jar` sits where
`stjp_core/config.py:SCRIBBLE_PATH` expects. Do **not** use the 2017
`org.scribble:scribble-dist:0.4.x` release from Maven Central: its parser
silently drops every protocol declaration, so validation passes on
*anything* — including deliberately broken protocols (verified with a
`Role not bound` case that 0.4.3 accepted and master rejects).

---

## Running the fork by hand

```bash
nuscr check  file.nuscr                       # well-formedness + balance
nuscr --enum file.nuscr                       # roles & protocols
nuscr project file.nuscr Role@Proto           # stock (inductive) projection
nuscr project --mode=coinductive-full file.nuscr Role@Proto   # the fork's value
nuscr --fsm=Role@Proto file.nuscr             # CFSM as Graphviz DOT
```

`--mode` accepts `inductive-full` (default nuscr behaviour),
`coinductive-full`, and `coinductive-plain`. The coinductive modes project
recursive receive-merges that stock projection leaves as a bare `rec` or
rejects outright — this is the concrete win of the fork for the loop-shaped
cases (`retry_loop`, `iterative_polling`, `nested_retry`).

Caveats (unchanged from the original integration):

- nuscr is **not** Scribble-compatible; `.scr` files go through the
  `stjp_core/compiler/nuscr_syntax.py` adapter, and nuscr accepts only a
  fragment (e.g. the finance protocol is rejected: "Non tail-recursive
  protocol not implemented"). The harness default therefore stays
  `scribble`; nuscr is opt-in per run.
- The binary prints `%%VERSION%%` for `--version` (the CI build skips
  `dune subst`); functionality is unaffected.
