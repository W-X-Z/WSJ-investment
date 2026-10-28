"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";

/** 화면의 부연 설명은 모두 여기로 (ADR-0023 개정): 카드·상세에는 값만 두고, 읽는 법은 ? 에 수납한다. */
const ENTRIES: { title: string; body: string }[] = [
  { title: "목표주가", body: "모형이 산출한 12개월 뒤 기대 주가입니다. 약세·기본·강세 시나리오마다 매출·마진·배수로 내재 주가를 내고 확률로 가중했습니다. 막대의 양 끝이 약세·강세, 점이 현재와 목표입니다. 매수·매도 권유가 아닙니다." },
  { title: "★ 검증 단계", body: "★1 가설(예측만 있음) · ★2 부분 확인(예측 1개 적중 또는 기업 자신의 공시로 경로 확인) · ★3 확인(적중 2개 이상 또는 기업 공식 숫자). 확신이 아니라 얼마나 검증됐는지입니다." },
  { title: "예측과 채점", body: "리포트마다 날짜 있는 예측 2~3개와 반증 조건 1개를 둡니다. 날짜가 오면 아침 실행이 채점하고, 적중은 ★를 올리고 반증 성립은 리포트를 닫습니다." },
  { title: "리포트가 만들어지는 법", body: "매일 아침: 공급망 이슈·공시·월매출·가격을 모으고 → 이슈마다 영향 경로를 최대 3개 세운 뒤 → 미국·한국 상장사가 붙은 경로를 골라 원문을 확인하고 → 리포트와 목표주가를 씁니다." },
  { title: "이슈 탭", body: "최근 이슈와 그 이슈가 공급망의 어느 고리를 바꾸는지(영향 경로)를 보여 줍니다. 경로 끝에 기업이 있으면 리포트로 이어집니다." },
];

export function HelpButton() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("mousedown", onDown); };
  }, [open]);
  return <div className="help" ref={ref}>
    <button type="button" className="help-btn" aria-expanded={open} aria-controls="help-panel" aria-label="읽는 법" onClick={() => setOpen((v) => !v)}>?</button>
    {open ? <div id="help-panel" className="help-panel" role="dialog" aria-label="읽는 법">
      <div className="help-head"><b>읽는 법</b><button type="button" onClick={() => setOpen(false)} aria-label="닫기"><Icon name="x" size={16}/></button></div>
      {ENTRIES.map((e) => <section key={e.title}><h4>{e.title}</h4><p>{e.body}</p></section>)}
      <p className="help-foot">개인 리서치 프로토타입 · 공개 자료 기반 · 투자 권유 아님</p>
    </div> : null}
  </div>;
}
