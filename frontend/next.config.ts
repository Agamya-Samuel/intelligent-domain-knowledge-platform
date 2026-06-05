import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["128.121.1.232"],
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        // Proxy all /api/v1/* requests to the backend
        source: "/api/v1/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
