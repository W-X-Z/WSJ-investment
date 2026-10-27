import Link from "next/link";
import { IdeaCard } from "@/components/IdeaCard";
import { ECO_KO, IDEA_TYPE, ago, loadIdeas } from "@/lib/ideas";

export const dynamic = "force-dynamic";
export const metadata = { title: "투자 아이디어" };

type SP = { eco?: string; type?: string };
const href = (sp: SP, patch: SP) => {
  const q = new URLSearchParams(Object.entries({ ...sp, ...patch }).filter(([, v]) => v) as [string, string][]).toString();
  return q ? `/?${q}` : "/";
};

/** 홈 = AI 투자 아이디어 피드 (ADR-0016). 결론(★·제목·두 문장·기업)을 먼저, 근거 사슬은 펼쳐서. */
export default async function Home({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const { ideas, source } = await loadIdeas();
  const shown = ideas.filter((x) => (!sp.eco || x.ecosystems.includes(sp.eco)) && (!sp.type || x.type === sp.type));
  const last = ideas.map((x) => x.updated_at).sort().at(-1);
  return <div className="ifeed">
    <header className="ifeed-head">
      <div>
        <div className="page-kicker">INVESTMENT IDEAS</div>
        <h1>지금 기회가 커지는 곳</h1>
        <p>최근 공시·뉴스·월매출·가격 변화를 공급망 그래프로 따라가 AI 가 매일 정리합니다.</p>
      </div>
      <div className="ifeed-meta">{source === "seed" ? "첫 아이디어 (자동 갱신 준비 중)" : `갱신 ${ago(last)}`} · {ideas.length}건</div>
    </header>
    <nav className="ifeed-filters" aria-label="아이디어 필터">
      <div>
        <Link className={!sp.eco ? "on" : ""} href={href(sp, { eco: undefined })}>전체</Link>
        {Object.entries(ECO_KO).map(([k, v]) => <Link key={k} className={sp.eco === k ? "on" : ""} href={href(sp, { eco: k })}>{v}</Link>)}
      </div>
      <div>
        {Object.entries(IDEA_TYPE).map(([k, v]) => <Link key={k} className={sp.type === k ? "on" : ""} href={href(sp, { type: sp.type === k ? undefined : k })}>{v.label}</Link>)}
      </div>
    </nav>
    <div className="ifeed-list">
      {shown.length ? shown.map((x, i) => <IdeaCard key={x.idea_key} idea={x} rank={i + 1}/>) : <div className="ifeed-empty">조건에 맞는 아이디어가 없습니다.</div>}
    </div>
    <footer className="ifeed-foot">
      <span>근거 데이터</span>
      <Link href="/feed">이슈 피드</Link><Link href="/indicators">가격·실적 지표</Link><Link href="/map">산업망 그래프</Link><Link href="/discovery">공급사 발굴</Link>
      <em>투자 판단을 돕는 정리이며 매수·매도 권유가 아닙니다.</em>
    </footer>
  </div>;
}
