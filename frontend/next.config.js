/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 本项目不使用 next/image；关闭图片优化接口，收掉 AVIF 优化链路的攻击面
  images: { unoptimized: true },
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

