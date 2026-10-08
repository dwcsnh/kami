import type { Metadata } from "next";
import Gallery from "./Gallery";

export const metadata: Metadata = { title: "kami · Thành phần giao diện" };

export default function Page() {
  return <Gallery />;
}
