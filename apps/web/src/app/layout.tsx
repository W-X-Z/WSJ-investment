import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "WSJ-investment console",
  description: "개발용 데이터 조회",
};

const NAV = [
  ["/", "개요"],
  ["/candidates", "후보"],
  ["/briefs", "브리프"],
  ["/signals", "신호"],
  ["/companies", "유니버스"],
  ["/insider", "내부자 거래"],
  ["/filings", "공시"],
  ["/finra", "수급(FINRA)"],
  ["/trials", "임상"],
  ["/fda", "FDA"],
  ["/awards", "정부계약"],
  ["/entities", "엔티티 매칭"],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="border-b border-neutral-200 bg-white">
          <nav className="max-w-screen-2xl mx-auto px-4 h-11 flex items-center gap-4">
            <span className="font-semibold mr-2">WSJ-investment</span>
            {NAV.map(([href, label]) => (
              <Link key={href} href={href} className="text-neutral-600 hover:text-neutral-900">
                {label}
              </Link>
            ))}
            <span className="ml-auto text-xs text-neutral-400">read-only · dev console</span>
          </nav>
        </header>
        <main className="max-w-screen-2xl mx-auto px-4 py-4">{children}</main>
      </body>
    </html>
  );
}
