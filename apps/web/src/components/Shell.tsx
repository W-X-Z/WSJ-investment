"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { HelpButton } from "@/components/Help";
import { Icon } from "@/components/Icon";

// 제품 (ADR-0028): 탭 둘 — 투자 아이디어(★·제목·아이디어·해석·근거) · 단서(출처에서 들어온 작은 소식). 결론과 결과만 — 방법론 화면은 메뉴에 두지 않는다
// (이전 화면들은 주소로는 그대로 열린다).
const NAV = [
  { href:"/", label:"투자 아이디어", icon:"lightbulb" },
  { href:"/clues", label:"단서", icon:"rss" },
] as const;
const LABELS: Record<string,string> = { "/":"투자 아이디어", "/clues":"단서", "/search":"통합 검색" };
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
  const section = path === "/" || path.startsWith("/opportunities") ? "/" : path.startsWith("/clues") ? "/clues" : path;
  const currentLabel = LABELS[section] ?? "투자 아이디어";
  const researchPage = path === "/" || path.startsWith("/opportunities");  // 투자 아이디어 (ADR-0028)
  return (
    <div className="workspace">
      {mobileOpen && <button className="mobile-scrim" onClick={()=>setMobileOpen(false)} aria-label="메뉴 닫기"/>}
      <aside className={`sidebar ${mobileOpen?"sidebar-open":""}`}>
        <Brand/>
        <div className="sidebar-section-title">WORKSPACE <span>01</span></div>
        <nav className="primary-nav" aria-label="주요 화면">
          {NAV.map(item=>{
            const active = item.href==="/" ? researchPage : path.startsWith(item.href);
            return <Link key={item.href} href={item.href} className={`nav-link ${active?"nav-link-active":""}`} aria-current={active?"page":undefined}>
              <Icon name={item.icon} size={17}/><span>{item.label}</span>{active && <i className="active-dot"/>}
            </Link>;
          })}
        </nav>
        <div className="sidebar-spacer"/>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={()=>setMobileOpen(v=>!v)} aria-label="메뉴 열기"><Icon name="menu" size={20}/></button>
            <span className="topbar-parent">WORKSPACE</span><Icon name="chevron-right" size={13} className="topbar-slash"/><span className="topbar-current">{currentLabel}</span>
          </div>
          <div className="topbar-right">
            <button className="search-shortcut" onClick={()=>setSearchOpen(true)}><Icon name="search" size={17}/><span>기술, 기업, 이슈 검색</span><kbd>⌘ K</kbd></button>
            <HelpButton/>
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
