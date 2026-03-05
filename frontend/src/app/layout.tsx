import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { LocaleProvider } from "@/lib/i18n/context";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MuteLens — AI Article Intelligence",
  description:
    "AI-powered article quality evaluation across 6 core dimensions. Uncover the true value of every article.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
