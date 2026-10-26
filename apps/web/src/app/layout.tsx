import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "SIGNAL ATLAS — 기술 변화에서 투자 가설까지", template: "%s | SIGNAL ATLAS" },
  description: "기술 생태계·공급망·실물 데이터·공개 근거를 연결하는 투자 리서치 워크스페이스",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
