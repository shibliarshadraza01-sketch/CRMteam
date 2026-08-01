import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Qualify Learn | Super Admin CRM",
  description: "Qualify Learn - Super Admin CRM panel",
  icons: {
    icon: "/qualify-learn-logo.jpeg"
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
