from wsj.ecosystems import coefficients as co


def test_kv_formulas_match_known_configs():
    assert co.kv_bytes_per_token({"attention": "gqa", "layers": 94, "kv_heads": 4, "head_dim": 128, "bytes_per_elem": 2}) == 192512  # Qwen3-235B
    assert co.kv_bytes_per_token({"attention": "mla", "layers": 61, "kv_lora_rank": 512, "qk_rope_head_dim": 64, "bytes_per_elem": 2}) == 70272  # DeepSeek-V3
    assert co.kv_bytes_per_token({"bytes_per_token_reported": 890}) == 890
    assert co.kv_bytes_per_token({"attention": "csa"}) is None


def test_growth_compression_and_scarcity():
    s = [{"metric": "m", "date": "2025-05", "value": 4.8e14}, {"metric": "m", "date": "2026-05", "value": 3.2e15}]
    g = co.annual_growth(s, "m")
    assert g["multiple"] == 6.67 and 6.5 < g["per_year"] < 6.8
    rows = [{"model": "a", "date": "2024-12-26", "bytes_per_token_reported": 35136}, {"model": "b", "date": "2026-09-10", "bytes_per_token_reported": 890}]
    c = co.compression(rows, ["a", "b"])
    assert c["multiple"] == round(890 / 35136, 4) and c["per_year"] < 0.2
    assert co.scarcity_index([{"date": "2026-09-18", "kind": "rationing"}, {"date": "2026-09-02", "kind": "price_up"},
                              {"date": "2026-07-30", "kind": "price_down"}]) == {"2026-07": -1, "2026-09": 3}


def test_shipped_table_loads_and_has_no_unsourced_rows():
    d = co.load()
    for section in ("arch_kv", "usage_series", "cache_price_ratio"):
        for r in d[section]:
            assert r["source"].startswith("https://") and r["verification"] in ("verified", "agent_reported", "derived")
    s = co.summary(d)
    assert s["usage_growth"]["per_year"] > 1 and s["kv_compression_deepseek_line"]["per_year"] < 1
