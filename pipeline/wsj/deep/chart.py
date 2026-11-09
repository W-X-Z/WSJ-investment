"""N24 주가 차트: 종가 선 + 주가 이슈 번호(story.moves 의 n)를 찍은 PNG. 노션 리포트의 시계열 옆에 붙인다.

글자는 영문·숫자만 쓴다(차트 글꼴에 한글이 없어도 깨지지 않게). 번호의 뜻은 리포트 글머리표가 맡는다.
matplotlib 이 필요하다: pip install -e '.[chart]'
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def render(story: dict[str, Any], out: str | Path, title: str | None = None) -> Path:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib 이 없다 — pip install -e '.[chart]'") from exc
    xs = [date.fromisoformat(p["date"]) for p in story["series"]]
    ys = [p["close"] for p in story["series"]]
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=160)
    ax.plot(xs, ys, color="#2b4c7e", linewidth=1.4)
    for m in story.get("moves") or []:
        d = date.fromisoformat(m["date"])
        up = (m.get("return_pct") or 0) >= 0
        ax.scatter([d], [m["close"]], s=46, color="#1f8a4c" if up else "#c23b22", zorder=3)
        ax.annotate(str(m["n"]), (d, m["close"]), textcoords="offset points", xytext=(0, 9 if up else -15),
                    ha="center", fontsize=8, fontweight="bold", color="#222")
    ax.set_title(title or f"{story['symbol']} close ({story['series'][0]['date']} ~ {story['series'][-1]['date']})", fontsize=10, loc="left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out
