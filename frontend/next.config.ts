import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: __dirname,
  },
  // 关闭开发左下角指示器
  devIndicators: false,
};

export default nextConfig;
