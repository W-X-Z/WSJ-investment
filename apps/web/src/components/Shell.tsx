"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";

// 제품 (ADR-0023): 탭 둘 — 리서치(기업 리포트 피드) · 이슈(최근 이슈와 공급망에서의 의미). 나머지는 '더 보기'에 수납한다.
const NAV = [
  { href:"/", label:"리서치", icon:"lightbulb" },
  { href:"/issues", label:"이슈", icon:"rss" },
] as const;
const MORE_ROUTES = [
  { href:"/bottlenecks", label:"병목 보드" },
  { href:"/indicators", label:"가격·실적 지표" },
  { href:"/map", label:"공급망 그래프" },
  { href:"/discovery", label:"공급사 발굴" },
  { href:"/briefs?kind=moat", label:"해자 카드" },
  { href:"/system", label:"시스템 점검" },
  { href:"/feed", label:"이슈 아카이브 (이전 화면)" },
] as const;
const RESEARCH_ROUTES = [
  { href:"/ecosystems", label:"기술 생태계 (이전 화면)" },
  { href:"/triggers", label:"트리거 추적 (이전 화면)" },
  { href:"/review", label:"기술 관계 검토 큐" },
  { href:"/history", label:"기술 자료 백필 아카이브" },
  { href:"/data", label:"연구 데이터 개요" },
  { href:"/briefs", label:"기업 분석 브리프" },
  { href:"/candidates", label:"기존 후보 스크리너" },
  { href:"/signals", label:"기업별 원천 신호" },
  { href:"/companies", label:"상장기업 유니버스" },
] as const;
const DEEP_ROUTES = [
  { href:"/filings", label:"SEC 공시" },{ href:"/insider", label:"내부자" },
  { href:"/finra", label:"공매도·수급" },{ href:"/fda", label:"FDA" },
  { href:"/trials", label:"임상" },{ href:"/awards", label:"정부 수주" },
  { href:"/entities", label:"기업명 매칭" },
] as const;
const LABELS: Record<string,string> = {
  "/":"리서치", "/issues":"이슈", "/map":"공급망 그래프", "/history":"과거 기술 아카이브", "/review":"기술 관계 검토", "/ecosystems":"기술 생태계", "/feed":"이슈 아카이브",
  "/ideas":"리서치 리포트", "/discovery":"공급사 발굴", "/indicators":"가격·실적 지표", "/triggers":"트리거", "/search":"통합 검색",
  "/data":"Research Data", "/briefs":"기업 브리프", "/bottlenecks":"병목 보드", "/system":"시스템 점검",
};
function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Signal Atlas 홈">
      <div className="brand-mark"><span className="brand-nucleus"/><span className="brand-beam"/><span className="brand-satellite"/></div>
      <span className="brand-words"><strong>SIGNAL<span>ATLAS</span></strong><small>TECHNOLOGY INTELLIGENCE</small></span>
    </Link>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [searchOpen,setSearchOpen] = useState(false);
  const [mobileOpen,setMobileOpen] = useState(false);
  const [search,setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(()=>{
    const handler=(e:KeyboardEvent)=>{
      if((e.metaKey || e.ctrlKey) && e.key.toLowerCase()==="k") {
        e.preventDefault();setSearchOpen(x=>!x);
      }
      if(e.key==="Escape"){setSearchOpen(false);setMobileOpen(false);}
    };
    window.addEventListener("keydown",handler);
    return ()=>window.removeEventListener("keydown",handler);
  },[]);
  useEffect(()=>{setMobileOpen(false);},[path]);
  useEffect(()=>{if(searchOpen)inputRef.current?.focus();},[searchOpen]);
  function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    const term=search.trim();
    setSearchOpen(false);
    router.push(term ? `/search?q=${encodeURIComponent(term)}` : "/search");
  }
  const section = path === "/" ? "/" : [...NAV, ...MORE_ROUTES].find(item=>item.href!=="/" && path.startsWith(item.href.split("?")[0]))?.href.split("?")[0] ?? path;
  const currentLabel = LABELS[section] ?? (path.startsWith("/ideas")?"리서치 리포트":path.startsWith("/issues/")?"이슈":path.startsWith("/ecosystems/")?"기술 생태계":path.startsWith("/feed/")?"이슈 아카이브":"리서치");
  const moreOpen = MORE_ROUTES.some(i=>path.startsWith(i.href.split("?")[0]));
  const legacyOpen = ["/review","/history","/data","/candidates","/briefs","/signals","/companies","/filings","/finra","/fda","/trials","/awards","/entities","/insider","/ecosystems","/triggers"].some(p=>path.startsWith(p));
  return (
    <div className="workspace">
      {mobileOpen && <button className="mobile-scrim" onClick={()=>setMobileOpen(false)} aria-label="메뉴 닫기"/>}
      <aside className={`sidebar ${mobileOpen?"sidebar-open":""}`}>
        <Brand/>
        <div className="sidebar-section-title">WORKSPACE <span>01</span></div>
        <nav className="primary-nav" aria-label="주요 화면">
          {NAV.map(item=>{
            const active = item.href==="/" ? path==="/" : path.startsWith(item.href);
            return <Link key={item.href} href={item.href} className={`nav-link ${active?"nav-link-active":""}`} aria-current={active?"page":undefined}>
              <Icon name={item.icon} size={17}/><span>{item.label}</span>{active && <i className="active-dot"/>}
            </Link>;
          })}
        </nav>
        <div className="sidebar-divider"/>
        <div className="sidebar-section-title">MORE <span>02</span></div>
        <details className="legacy-group" open={moreOpen || legacyOpen || undefined}>
          <summary className="legacy-trigger"><Icon name="layers" size={17}/><span>더 보기 — 근거·도구</span><Icon name="chevron-down" size={14}/></summary>
          <div className="legacy-links">
            {MORE_ROUTES.map(i=><Link key={i.href} href={i.href} className={path.startsWith(i.href.split("?")[0])?"legacy-active":""}>{i.label}</Link>)}
            <details className="legacy-subgroup" open={legacyOpen || undefined}>
              <summary>데이터 워크스페이스 <Icon name="chevron-down" size={13}/></summary>
              <div className="legacy-links nested">
                {RESEARCH_ROUTES.map(i=><Link key={i.href} href={i.href} className={path===i.href?"legacy-active":""}>{i.label}</Link>)}
                {DEEP_ROUTES.map(i=><Link key={i.href} href={i.href}>{i.label}</Link>)}
              </div>
            </details>
          </div>
        </details>
        <div className="sidebar-spacer"/>
        <div className="sidebar-footnote"><span className="pulse-ring"/><div><strong>RESEARCH WORKSPACE</strong><p>공개 근거 기반 공급망 리서치<br/>목표주가는 모형 산출 · 매매 권유 아님</p></div></div>
        <div className="sidebar-bottom">© 2026 SIGNAL ATLAS <span>v1.0</span></div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={()=>setMobileOpen(v=>!v)} aria-label="메뉴 열기"><Icon name="menu" size={20}/></button>
            <span className="topbar-parent">WORKSPACE</span><Icon name="chevron-right" size={13} className="topbar-slash"/><span className="topbar-current">{currentLabel}</span>
          </div>
          <div className="topbar-right">
            <button className="search-shortcut" onClick={()=>setSearchOpen(true)}><Icon name="search" size={17}/><span>기술, 기업, 이슈 검색</span><kbd>⌘ K</kbd></button>
            <span className="topbar-date">RESEARCH · 2026</span>
            <span className="topbar-avatar" title="Research Workspace">R</span>
          </div>
        </header>
        <main id="main" className="main-content">{children}</main>
      </div>
      {searchOpen && <div className="palette-backdrop" onMouseDown={(e)=>{if(e.target===e.currentTarget)setSearchOpen(false);}}>
        <div className="palette" role="dialog" aria-modal="true" aria-label="통합 검색">
          <form onSubmit={submit} className="palette-form"><Icon name="search" size={21}/><input ref={inputRef} placeholder="기술, 기업, 공정, 트리거 검색…" value={search} onChange={e=>setSearch(e.target.value)}/><button type="button" onClick={()=>setSearchOpen(false)} aria-label="닫기"><Icon name="x" size={18}/></button></form>
          <p className="palette-hint">검색어를 입력하고 Enter · 기업 티커, 기술명, 소재, 병목 모두 검색</p>
          <div className="palette-quick">
            <span>빠른 탐색</span>
            {[["HBM4","/search?q=HBM"],["광통신","/search?q=광"],["800VDC","/search?q=800V"],["CAMT","/search?q=CAMT"]].map(([label,href])=><Link key={label} href={href} onClick={()=>setSearchOpen(false)}><Icon name="arrow-up-right" size={14}/>{label}</Link>)}
          </div>
        </div>
      </div>}
    </div>
  );
}
