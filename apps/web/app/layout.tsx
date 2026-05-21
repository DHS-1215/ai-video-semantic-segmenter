import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI \u89c6\u9891\u8bed\u4e49\u5206\u6bb5\u7cfb\u7edf",
  description:
    "\u4e0a\u4f20\u957f\u89c6\u9891\u540e\uff0c\u7cfb\u7edf\u4f1a\u7406\u89e3\u89c6\u9891\u4e2d\u7684\u8bf4\u8bdd\u5185\u5bb9\uff0c\u5e76\u6309\u5b8c\u6574\u8bdd\u9898\u62c6\u5206\u4e3a\u8bed\u4e49\u7247\u6bb5\u3002",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
