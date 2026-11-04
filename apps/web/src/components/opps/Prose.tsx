/** 본문을 문단으로 — 서버·클라이언트 양쪽에서 쓴다 (server-only 의존 없음). */
/** 문단 머리의 짧은 표지 — "단서:", "시장이 믿는 것과 우리:", "가장 약한 고리:". 에이전트가 쓴 구조를 그대로 보이게 굵게만 한다. */
const LABEL = /^([^:：\n.]{1,18})[:：]\s+/;
const SENTENCE_END = /(?<=[.!?])\s+(?=[가-힣A-Z0-9"'(])/;

/** 긴 본문을 문단으로. 줄바꿈이 있으면 그대로, 없으면(옛 글) 세 문장씩 끊는다 — 한 덩어리로 찍히지 않게. */
export function paragraphs(text: string): string[] {
  const byLine = text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  if (byLine.length > 1 || text.length < 450) return byLine;
  const sents = text.split(SENTENCE_END).map((s) => s.trim()).filter(Boolean);
  const out: string[] = [];
  for (let i = 0; i < sents.length; i += 3) out.push(sents.slice(i, i + 3).join(" "));
  return out;
}

export function Prose({ text }: { text: string }) {
  return <div className="op-prose">{paragraphs(text).map((p, i) => {
    const m = p.match(LABEL);
    return <p key={i}>{m ? <><b>{m[1]}</b>{p.slice(m[0].length)}</> : p}</p>;
  })}</div>;
}

