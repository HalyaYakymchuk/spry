import type { Metadata } from "next";
import "./globals.css";
import { AppProviders } from "./providers";

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
        <AppProviders>
          {children}
        </AppProviders>
      </body>
    </html>
  );
}