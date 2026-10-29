import { CHAIN_KO, loadSystem } from "@/lib/system";
import { WATCH_STATUS_KO } from "@/lib/ideas";
import { rel } from "@/lib/feed";

export const dynamic = "force-dynamic";
export const metadata = { title: "시스템 점검" };

const SEV = { 3: "높음", 2: "중간", 1: "낮음" } as const;
const KIND_KO: Record<string, string> = { data: "데이터", ontology: "온톨로지", judgment: "판단", ui: "화면", ops: "운영" };

/** 시스템 점검 (ADR-0017): 고칠 것 → 수집 상태 → 데이터 커버리지 → 판단 성적 → 스스로 고친 기록. */
export default async function SystemPage() {
  const s = await loadSystem();
  const hit = s.judgment.record.hit ?? 0, miss = s.judgment.record.miss ?? 0;
  return <div className="fd">
    <header className="fd-head">
      <div className="page-kicker">시스템 점검</div>
      <h1>데이터가 들어오고, 판단이 쌓이고 있나</h1>
      <p className="fd-summary">{s.problems.length ? `고칠 것 ${s.problems.length}건` : "고칠 것 없음"} · 가격 {s.prices.covered}/{s.prices.listed} 종목 · 그래프 {s.graph.nodes} 노드 / {s.graph.edges} 관계
        {` · 확인 일정 적중 ${hit} · 빗나감 ${miss}`}</p>
    </header>

    <section className="fd-sec">
      <h2>고칠 것<small>매주 개선 예약작업이 위에서부터 고칩니다</small></h2>
      {s.problems.length ? <ul className="sys-problems">{s.problems.map((p, i) => <li key={i} className={`sev-${p.severity}`}>
        <span>{SEV[p.severity]}</span><b>{p.area}</b>{p.what}</li>)}</ul> : <p className="fd-empty">지금은 없습니다.</p>}
    </section>

    <section className="fd-sec">
      <h2>오늘 아침 사슬<small>수집 → 영향 경로 → 조사 → 리포트·목표주가 → 검증·보고 (KST, ADR-0024)</small></h2>
      <ol className="sys-chain">{s.chain.map((c) => <li key={c.task} className={`st-${c.status ?? "none"}`}>
        <b>{CHAIN_KO[c.task]}</b><span>{c.status === "succeeded" ? "완료" : c.status === "skipped" ? "할 일 없음" : c.status === "failed" ? "실패" : c.status === "running" ? "진행 중" : "아직"}</span>
        {c.rows != null && c.status === "succeeded" ? <small>{c.rows}건</small> : null}{c.started_at ? <small>{rel(c.started_at)}</small> : null}
        {c.error ? <em>{c.error}</em> : null}</li>)}</ol>
    </section>

    <section className="fd-sec">
      <h2>수집 상태<small>최근 45일 · 매일 돌아야 하는 수집기 먼저</small></h2>
      {s.collectors.length ? <div className="sys-table" role="table">
        <div className="sys-tr sys-th" role="row"><span>수집기</span><span>마지막 성공</span><span>행</span><span>7일 실패</span><span>최근 오류</span></div>
        {s.collectors.map((c) => <div key={c.name} className="sys-tr" role="row">
          <span><b>{c.name}</b>{c.daily ? <small> 매일</small> : null}</span><span>{c.lastOk ? rel(c.lastOk) : "없음"}</span><span>{c.lastRows ?? "—"}</span>
          <span className={c.fails7 ? "fd-warn" : ""}>{c.fails7}</span><span className="sys-err">{c.lastError ?? ""}</span>
        </div>)}
      </div> : <p className="fd-empty">{s.runsMissing ? "수집 기록 뷰(0021)가 아직 없습니다." : "기록이 없습니다."}</p>}
    </section>

    <section className="fd-sec">
      <h2>데이터 커버리지</h2>
      <div className="sys-grid">
        <div><h3>가격 (최근 7일)</h3><ul>{s.prices.byMarket.map(([m, [a, b]]) => <li key={m}>{m} <b>{a}/{b}</b></li>)}
          {s.prices.noSource ? <li>출처 없는 거래소 <b>{s.prices.noSource}</b></li> : null}
          <li>시가총액 있음 <b>{s.prices.withCap}/{s.prices.listed}</b></li>
          <li>룸 조건 통과 <b>{s.prices.tenbaggers}</b> <small>(시총 $3B 이하 · 1년 저점 대비 3배 미만)</small></li></ul></div>
        <div><h3>지표</h3><ul>{s.indicators.byCat.map(([c, n]) => <li key={c}>{c} <b>{n}</b></li>)}
          <li>갱신 늦음 <b>{s.indicators.stale}</b></li><li>값 없음 <b>{s.indicators.empty}</b></li></ul></div>
        <div><h3>그래프</h3><ul><li>병목 <b>{s.graph.bottlenecks}</b></li><li>상장사로 안 이어지는 병목 <b>{s.graph.dead.length}</b></li></ul></div>
      </div>
    </section>

    <section className="fd-sec">
      <h2>판단 성적<small>아이디어의 근거 점수와 확인 일정 결과</small></h2>
      <div className="sys-grid">
        <div><h3>근거 점수 ({s.judgment.scores.length}/{s.judgment.ideas})</h3>
          <p className="sys-scores">{s.judgment.scores.length ? [...s.judgment.scores].sort((a, b) => b - a).join(" · ") : "아직 계산 전"}</p></div>
        <div><h3>확인 일정</h3><ul>{Object.entries(s.judgment.record).map(([k, n]) => <li key={k}>{WATCH_STATUS_KO[k] ?? k} <b>{n}</b></li>)}</ul></div>
      </div>
    </section>

    <section className="fd-sec">
      <h2>스스로 고친 기록<small>예약작업과 세션이 남긴 개선 — 데이터·온톨로지 변경은 PR 로 남습니다</small></h2>
      <ol className="sys-log">{s.log.map((e, i) => <li key={i}><span className="fd-date">{e.date.slice(5).replace("-", "/")}</span>
        <b>{KIND_KO[e.kind] ?? e.kind}</b>{e.title}{e.pr ? <a href={`https://github.com/W-X-Z/WSJ-investment/pull/${e.pr}`} target="_blank" rel="noreferrer"> #{e.pr}</a> : null}
        {e.detail ? <p>{e.detail}</p> : null}</li>)}</ol>
    </section>
  </div>;
}
