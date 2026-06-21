import "./globals.css";
import type { Metadata } from "next";
import ToastContainer from "@/components/ui/Toast";
import SessionBootstrap from "@/components/layout/SessionBootstrap";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "ResumeAI · 智能简历修改",
  description: "JD 驱动的简历智能修改工具，导出 A4 单页 PDF",
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
