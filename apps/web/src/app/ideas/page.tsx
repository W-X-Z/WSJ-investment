import { redirect } from "next/navigation";

/** 투자 아이디어 피드는 홈이다 (ADR-0016). */
export default function Ideas() {
  redirect("/");
}
