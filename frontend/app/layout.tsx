import "./globals.css";
import type { Metadata } from "next";
import ToastContainer from "@/components/ui/Toast";
import SessionBootstrap from "@/components/layout/SessionBootstrap";
import AppShell from "@/components/layout/AppShell";
import { copy } from "@/lib/copy";

export const metadata: Metadata = {
  title: `${copy.product.name} · ${copy.product.tagline}`,
  description: copy.product.metaDescription,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <SessionBootstrap />
        <AppShell>{children}</AppShell>
        <ToastContainer />
      </body>
    </html>
  );
}
