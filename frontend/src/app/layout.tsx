import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LeKai教案知识库",
  description: "小学语文教案智能生成平台 — 基于统编版教材，为福建宁德教师服务",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="font-sans antialiased bg-amber-50 text-gray-900 min-h-screen">
        {children}
      </body>
    </html>
  );
}
