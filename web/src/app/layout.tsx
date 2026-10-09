import { AppShell } from "@/manager/AppShell";
import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./shadcn.css";
import "@/design/tokens.css";
import "./globals.css";

// Self-hosted by next/font at build time; tabular figures are enabled in globals.css.
const inter = Inter({ subsets: ["latin", "vietnamese"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "kami · Simulation manager",
  description: "Phát lại mô phỏng vận hành đội xe GreenSM tại Hà Nội (kami 0.2)",
};

export const viewport: Viewport = { themeColor: "#0ABAB5", colorScheme: "light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={inter.variable}>
      <body><TooltipProvider><AppShell>{children}</AppShell></TooltipProvider></body>
    </html>
  );
}
