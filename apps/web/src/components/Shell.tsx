"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { HelpButton } from "@/components/Help";
import { Icon } from "@/components/Icon";

// 제품 (ADR-0028): 결론과 결과만 메뉴에 둔다 — 방법론·운영 화면(시스템 점검, 유니버스 표, 후보 점수…)은 주소로만 연다.
// 읽기: 투자 아이디어(★·제목·아이디어·해석·근거) · 단서(출처에서 들어온 작은 소식).
// 탐색: 병목(어디가 조여지고 누가 길목에 있나) · 생태계(세 공급망의 기술 지도) · 공급망 지도(전체 그래프 캔버스). 2026-11-04 사용자 요청으로 진입 동선 추가.
type NavItem = { href: string; label: string; icon: "lightbulb" | "rss" | "filter" | "layers" | "network"; match: (p: string) => boolean };
const NAV: { title: string; items: NavItem[] }[] = [
  { title: "읽기", items: [
    { href: "/", label: "투자 아이디어", icon: "lightbulb", match: (p) => p === "/" || p.startsWith("/opportunities") },
    { href: "/clues", label: "단서", icon: "rss", match: (p) => p.startsWith("/clues") },
  ] },
  { title: "탐색", items: [
    { href: "/bottlenecks", label: "병목", icon: "filter", match: (p) => p.startsWith("/bottlenecks") },
    { href: "/ecosystems", label: "생태계", icon: "layers", match: (p) => p.startsWith("/ecosystems") || p.startsWith("/companies") },
    { href: "/map", label: "공급망 지도", icon: "network", match: (p) => p.startsWith("/map") },
  ] },
];
const EXTRA_LABELS: Record<string, string> = { "/search": "통합 검색", "/system": "시스템 점검", "/ideas": "리포트", "/companies": "기업" };
function current(path: string): { group: string; label: string } {
  for (const g of NAV) for (const it of g.items) if (it.match(path)) return { group: g.title, label: it.label };
  const k = Object.keys(EXTRA_LABELS).find((p) => path.startsWith(p));
  return { group: "", label: k ? EXTRA_LABELS[k] : "" };
}
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
  const here = current(path);
  return (
    <div className="workspace">
      {mobileOpen && <button className="mobile-scrim" onClick={()=>setMobileOpen(false)} aria-label="메뉴 닫기"/>}
      <aside className={`sidebar ${mobileOpen?"sidebar-open":""}`}>
        <Brand/>
        <nav className="primary-nav" aria-label="주요 화면">
          {NAV.map((g) => <div key={g.title} className="nav-group">
            <div className="nav-group-title">{g.title}</div>
            {g.items.map((item) => {
              const active = item.match(path);
              return <Link key={item.href} href={item.href} className={`nav-link ${active ? "nav-link-active" : ""}`} aria-current={active ? "page" : undefined}>
                <Icon name={item.icon} size={18}/><span>{item.label}</span>
              </Link>;
            })}
          </div>)}
        </nav>
        <div className="sidebar-spacer"/>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={()=>setMobileOpen(v=>!v)} aria-label="메뉴 열기"><Icon name="menu" size={20}/></button>
            {here.group ? <><span className="topbar-parent">{here.group}</span><Icon name="chevron-right" size={13} className="topbar-slash"/></> : null}
            <span className="topbar-current">{here.label}</span>
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
