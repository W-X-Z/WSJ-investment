"""리서치 에이전트용 결정론적 도구 — 숫자를 글로 계산하지 않고 코드로 재현 가능하게 얻는다.

CLI:    python -m wsj tools <quote|history|lookup|fx|rates|event|exposure|reverse-dcf|peers|incremental> --help
Python: from wsj.tools import quote, history, lookup, fx, rates, event, exposure, reverse_dcf, dcf_value, peers, incremental_run

모든 함수는 dict(JSON 직렬화 가능)를 돌려준다. 네트워크가 필요한 함수는 ctx=ToolContext 를 받아 연결·환율·티커표를 재사용한다
(open_context() 참고). 키(API key)는 필요 없다. Supabase 키가 있으면 raw.px_daily 등을 읽기 전용으로 먼저 본다.
"""

from wsj.tools.context import ToolContext, ToolError, open_context
from wsj.tools.dcf import dcf_value, implied_cagr, reverse_dcf
from wsj.tools.event import event
from wsj.tools.exposure import exposure
from wsj.tools.fx import fx
from wsj.tools.incremental import evaluate as incremental_evaluate
from wsj.tools.incremental import run as incremental_run
from wsj.tools.lookup import lookup
from wsj.tools.peers import peers
from wsj.tools.prices import history, parse_symbol
from wsj.tools.quote import quote
from wsj.tools.rates import rates

__all__ = [
    "ToolContext", "ToolError", "open_context", "quote", "history", "lookup", "fx", "rates", "event", "exposure",
    "reverse_dcf", "dcf_value", "implied_cagr", "peers", "incremental_run", "incremental_evaluate", "parse_symbol",
]
