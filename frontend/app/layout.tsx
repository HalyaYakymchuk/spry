import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spry - Meeting Scheduler & Analytics",
  description: "View and schedule meetings with ease",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
