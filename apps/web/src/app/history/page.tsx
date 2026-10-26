import Link from "next/link";
import { Icon } from "@/components/Icon";
import historical from "@/data/historical-evidence.json";
type SP={q?:string;eco?:string;year?:string;source?:string;page?:string};
type Row={id:string;title:string;published_at:string;url:string;source:string;ecosystem:string;kind:string;excerpt:string;first_seen_at:string;published_precision?:string;historical_backfill:boolean};
const DATA=historical as unknown as {summary:{
  records:number;historical_period:number[];by_source:Record<string,number>;
  by_ecosystem:Record<string,number>;by_publication_year:Record<string,number>;
  failed_source_segments:unknown[];status:string;collected_at:string
}|null;events:Row[]};
const SOURCES=["openalex","crossref","sec","federalregister"];
const ECO={hbm:"HBM·반도체 패키징",optics:"광통신·포토닉스",power:"전력·전력반도체"} as Record<string,string>;
export const metadata={title:"과거 기술 자료 아카이브 | Signal Atlas"};
function displayedDate(record:Row):string{
 const date=record.published_at;
 return record.published_precision==="year"?date.slice(0,4)+"년 (연도만 확인)"
 :record.published_precision==="month"?date.slice(0,7)+" (월까지 확인)":date;
}
export default async function History({searchParams}:{searchParams:Promise<SP>}){
 const sp=await searchParams;
 const q=(sp.q??"").trim().toLowerCase();
 const eco=sp.eco??"",year=sp.year??"",source=sp.source??"";
 const rawPage=Number(sp.page??1),page=Number.isSafeInteger(rawPage)?Math.min(40,Math.max(1,rawPage)):1;
 const rows=DATA.events.filter(x=>(!eco||x.ecosystem===eco)&&(!year||x.published_at.startsWith(year))&&(!source||x.source===source)&&(!q||(x.title+" "+x.excerpt+" "+x.source).toLowerCase().includes(q)));
 const per=25,totalPages=Math.max(1,Math.ceil(rows.length/per));
 const shown=rows.slice((Math.min(page,totalPages)-1)*per,Math.min(page,totalPages)*per);
 const linkPage=(p:number)=>"/history?"+new URLSearchParams({q:sp.q??"",eco,year,source,page:String(p)}).toString();
 return <div className="history-screen">
   <div className="map-screen-header"><div><div className="page-kicker">HISTORICAL RESEARCH ARCHIVE / 2020—2026</div><h1>기술 변화의 과거 기록</h1><p>최근 이슈가 발생하기 전, 어떤 연구·특허·공시가 이미 공개됐는지 기간과 분야별로 추적합니다.</p></div>
    <Link href="/map" className="outline-button"><Icon name="network" size={17}/> 산업망 캔버스</Link>
   </div>
   <div className="history-summary">
    <div><span>수집한 공개 원천</span><strong>{(DATA.summary?.records??0).toLocaleString("ko-KR")}</strong><small>원문 검증 전 · 제한된 검색 결과</small></div>
    <div><span>연구 생태계</span><strong>{Object.keys(DATA.summary?.by_ecosystem??{}).length}</strong><small>HBM · 광통신 · 전력</small></div>
    <div><span>연구 기간</span><strong>{DATA.summary?.historical_period?.join("–")??"조회 전"}</strong><small>발표일 기준 · 수집일 별도</small></div>
    <div><span>웹 탐색 인덱스</span><strong>{DATA.events.length.toLocaleString("ko-KR")}</strong><small>연도·소스별 균형 표본</small></div>
   </div>
   <div className="history-year-bars" aria-label="연도별 백필 자료">
     {Object.entries(DATA.summary?.by_publication_year??{}).map(([y,n])=><Link key={y} href={`/history?year=${y}`} className={year===y?"active":""}><span>{y}</span><i style={{height:`${Math.max(8,Math.min(80,n/12))}px`}}/><strong>{n}</strong></Link>)}
   </div>
   <form className="history-filters" action="/history" method="get">
    <label><Icon name="search" size={17}/><input name="q" aria-label="과거 자료 검색" placeholder="검색어: wafer, SiC, transceiver, bonding..." defaultValue={sp.q??""}/></label>
    <select name="eco" aria-label="생태계" defaultValue={eco}><option value="">전체 생태계</option>{Object.entries(ECO).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
    <select name="year" aria-label="발표 연도" defaultValue={year}><option value="">전체 기간</option>{Object.keys(DATA.summary?.by_publication_year??{}).map(y=><option value={y} key={y}>{y}년</option>)}</select>
    <select name="source" aria-label="원천" defaultValue={source}><option value="">모든 출처</option>{SOURCES.map(s=><option value={s} key={s}>{s}</option>)}</select>
    <button type="submit"><Icon name="filter" size={15}/> 적용</button>
    <Link href="/history" aria-label="필터 초기화">초기화</Link>
   </form>
   <div className="history-notice"><Icon name="info" size={17}/><span>이 화면은 전체 {(DATA.summary?.records??0).toLocaleString("ko-KR")}건 중 <strong>연도·출처별 표본 {DATA.events.length}건</strong>을 보여줍니다. 전체 JSONL 자료는 <a href="https://github.com/W-X-Z/WSJ-investment/tree/feat/historical-backfill-graph-canvas-20261026/research/backfill" target="_blank" rel="noreferrer">GitHub 백필 저장소</a>에서 확인할 수 있습니다. 학술 색인은 논문 결과의 독립 검증이 아닙니다.</span></div>
   <div className="history-list">{shown.length?shown.map(row=><article key={row.id} className="history-row"><div className="history-row-date"><strong>{row.published_at.slice(0,4)}</strong><span>{row.published_precision==="year"?"연도만":row.published_precision==="month"?row.published_at.slice(5,7)+"월":row.published_at.slice(5)}</span></div><div><div className="history-row-tags"><span>{ECO[row.ecosystem]??row.ecosystem}</span><span>{row.source.toUpperCase()}</span><span>{row.kind}</span></div><a href={row.url} target="_blank" rel="noreferrer" className="history-row-title">{row.title}<Icon name="arrow-up-right" size={15}/></a><p>{row.excerpt||"원문 연구 전 메타데이터"}</p><small>발표일 {displayedDate(row)} · 최초 관측 {row.first_seen_at.slice(0,10)} · 역사적 데이터 재수집</small></div></article>):<div className="history-empty">검색 조건에 맞는 공개자료가 없습니다. 다른 연도·산업·검색어를 선택하세요.</div>}</div>
   <div className="history-page-controls"><span>{rows.length}건 중 {shown.length}건 표시 · {Math.min(page,totalPages)}/{totalPages} 페이지</span><div>{page>1&&<Link href={linkPage(page-1)}>이전</Link>}{page<totalPages&&<Link href={linkPage(page+1)}>다음</Link>}</div></div>
 </div>;
}
