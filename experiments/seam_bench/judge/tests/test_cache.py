from __future__ import annotations

from experiments.seam_bench.judge.cache import VerdictCache, cache_key


def test_get_or_compute_is_pure_cache_hit_on_rerun(tmp_path):
    cache = VerdictCache(tmp_path / "c")
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"vote": "yes"}

    key = cache_key("fwd", "claude-opus-4-8", 0.3, "prompt_h", "payload_h")
    v1 = cache.get_or_compute(key, compute)
    v2 = cache.get_or_compute(key, compute)
    v3 = cache.get_or_compute(key, compute)

    assert v1 == v2 == v3 == {"vote": "yes"}
    assert calls["n"] == 1, "second and third calls must be pure cache hits"
    assert cache.stats.hits == 2
    assert cache.stats.misses == 1


def test_rerun_across_fresh_cache_instances_is_still_a_hit(tmp_path):
    """Reruns must be pure cache hits even from a brand-new process/object
    against the same cache_dir — the whole point of an on-disk cache."""
    cache_dir = tmp_path / "c"
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"vote": "no"}

    key = cache_key("back", "claude-sonnet-5", 0.7, "p", "g")
    VerdictCache(cache_dir).get_or_compute(key, compute)
    VerdictCache(cache_dir).get_or_compute(key, compute)  # fresh instance

    assert calls["n"] == 1


def test_different_keys_do_not_collide(tmp_path):
    cache = VerdictCache(tmp_path / "c")
    k1 = cache_key("fwd", "claude-opus-4-8", 0.3, "prompt_a", "payload_x")
    k2 = cache_key("fwd", "claude-opus-4-8", 0.7, "prompt_a", "payload_x")  # temp differs
    k3 = cache_key("fwd", "claude-opus-4-8", 0.3, "prompt_b", "payload_x")  # prompt differs
    k4 = cache_key("back", "claude-opus-4-8", 0.3, "prompt_a", "payload_x")  # class differs

    cache.put(k1, "A")
    assert cache.get(k2) is None
    assert cache.get(k3) is None
    assert cache.get(k4) is None
    assert cache.get(k1) == "A"


def test_clear_resets_cache_and_stats(tmp_path):
    cache = VerdictCache(tmp_path / "c")
    key = cache_key("fwd", "m", 0.3, "p", "g")
    cache.put(key, {"vote": "yes"})
    assert cache.get(key) is not None
    cache.clear()
    assert cache.get(key) is None
    assert cache.stats.hits == 0
