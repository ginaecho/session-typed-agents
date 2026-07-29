"""slug_util.sanitize keeps generated filenames portable (Windows MAX_PATH).

Regression guard for the over-long evidence-sidecar filename that made
`git clone` fail on Windows ("Filename too long").
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from slug_util import sanitize, MAX_SLUG_LEN  # noqa: E402


def test_short_names_pass_through_unchanged():
    assert sanitize("explicit_ref:github/awesome-copilot:gem-implementer+r") == \
        "explicit_ref_github_awesome_copilot_gem_implementer_r"


def test_long_name_is_capped_and_still_filesystem_safe():
    long_id = "explicit_ref:github/awesome-copilot:" + "+".join(f"role-{i}" for i in range(60))
    out = sanitize(long_id)
    assert len(out) <= MAX_SLUG_LEN
    assert all(c.isalnum() or c == "_" for c in out)


def test_distinct_long_names_do_not_collide():
    a = "team-" + "x" * 300 + "-alpha"
    b = "team-" + "x" * 300 + "-beta"
    assert sanitize(a) != sanitize(b)
    assert len(sanitize(a)) <= MAX_SLUG_LEN
    assert len(sanitize(b)) <= MAX_SLUG_LEN


def test_regression_the_team_id_that_broke_git_clone():
    # The exact team_id that slugified to a 226-char basename / 282-char path.
    team_id = (
        "explicit_ref:github/awesome-copilot:agent-safety+agents+debug+"
        "devbox-image-definition+gem-critic+gem-debugger+gem-documentation-writer+"
        "gem-orchestrator+gem-planner+gem-reviewer+gem-skill-creator+plan+planner+prd+prompt"
    )
    filename = f"09_{sanitize(team_id)}.json"
    # "NN_" (3) + capped slug + ".json" (5) stays comfortably short.
    assert len(filename) <= MAX_SLUG_LEN + 10
