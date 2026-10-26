"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";

const NAV = [
  { href:"/", label:"인사이트 홈", icon:"grid" },
  { href:"/map", label:"산업망 캔버스", icon:"network" },
  { href:"/ecosystems", label:"기술 생태계", icon:"layers" },
  { href:"/feed", label:"이슈 피드", icon:"rss" },
  { href:"/discovery", label:"공급사 발굴", icon:"search" },
  { href:"/ideas", label:"투자 가설", icon:"lightbulb" },
  { href:"/triggers", label:"트리거 추적", icon:"radar" },
] as const;
const RESEARCH_ROUTES = [
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
  "/":"Overview", "/map":"산업망 캔버스", "/history":"과거 기술 아카이브", "/review":"기술 관계 검토", "/ecosystems":"기술 생태계", "/feed":"이슈 피드",
  "/ideas":"투자 가설", "/discovery":"공급사 발굴", "/triggers":"트리거", "/search":"통합 검색",
  "/data":"Research Data", "/briefs":"기업 브리프",
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
  const section = path === "/" ? "/" : NAV.find(item=>item.href!=="/" && path.startsWith(item.href))?.href ?? path;
  const currentLabel = LABELS[section] ?? (path.startsWith("/ecosystems/")?"기술 생태계":path.startsWith("/feed/")?"이슈 분석":"리서치");
  const legacyOpen = ["/review","/history","/data","/candidates","/briefs","/signals","/companies","/filings","/finra","/fda","/trials","/awards","/entities","/insider"].some(p=>path.startsWith(p));
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
        <div className="sidebar-section-title">RESEARCH ARCHIVE <span>02</span></div>
        <details className="legacy-group" open={legacyOpen || undefined}>
          <summary className="legacy-trigger"><Icon name="database" size={17}/><span>데이터 워크스페이스</span><Icon name="chevron-down" size={14}/></summary>
          <div className="legacy-links">
            {RESEARCH_ROUTES.map(i=><Link key={i.href} href={i.href} className={path===i.href?"legacy-active":""}>{i.label}</Link>)}
            <details className="legacy-subgroup">
              <summary>원천 데이터 더 보기 <Icon name="chevron-down" size={13}/></summary>
              <div className="legacy-links nested">{DEEP_ROUTES.map(i=><Link key={i.href} href={i.href}>{i.label}</Link>)}</div>
            </details>
          </div>
        </details>
        <div className="sidebar-spacer"/>
        <div className="sidebar-footnote"><span className="pulse-ring"/><div><strong>RESEARCH WORKSPACE</strong><p>공개 근거 기반 기술 분석<br/>기업가치 예측·매매 실행 아님</p></div></div>
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
