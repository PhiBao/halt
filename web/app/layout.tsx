import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HALT — Circuit Breaker for the Agentic Economy",
  description: "Neutral, decentralized emergency halt for autonomous payment agents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
