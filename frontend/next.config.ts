import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // 关闭开发左下角指示器
  devIndicators: false,
  // 开发时 API 代理到后端
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
