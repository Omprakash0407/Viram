import type { Metadata } from "next";
import { Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { SessionProviderBridge } from "./components/SessionProviderBridge";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "VIRĀM — A Pause You Need",
  description:
    "Discover India's soul through its places, people and culture. Your intelligent travel companion.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${jakarta.variable} antialiased`}>
        <SessionProviderBridge>{children}</SessionProviderBridge>
      </body>
    </html>
  );
}
