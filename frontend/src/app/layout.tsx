import type { Metadata } from "next";
import { Rajdhani } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const rajdhani = Rajdhani({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const rajdhaniMono = Rajdhani({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "IDKP — Intelligent Domain Knowledge Platform",
  description:
    "Production-grade open-source AI question-answering system with fine-tuned LLMs and Advanced RAG.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${rajdhani.variable} ${rajdhaniMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
