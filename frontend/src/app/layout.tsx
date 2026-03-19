import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BI Agent — Monday.com Intelligence",
  description: "AI-powered business intelligence over Monday.com data",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
