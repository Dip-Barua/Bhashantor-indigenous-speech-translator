import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bhashantor — ভাষান্তর",
  description: "Inclusive multilingual speech and translation for the Chittagong Hill Tracts",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/bhashantor-icon.png", shortcut: "/bhashantor-icon.png", apple: "/bhashantor-icon.png" },
};

export const viewport: Viewport = { themeColor: "#ecfdf5" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
