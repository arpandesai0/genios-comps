import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  devIndicators: false,
  outputFileTracingIncludes: { "/api/**/*": ["./mocks/*.json"] },
  async rewrites() {
    return {
      beforeFiles:
        process.env.NEXT_PUBLIC_USE_MOCKS === "0"
          ? [
              {
                source: "/api/:path*",
                destination: `${process.env.API_URL || "http://localhost:8000"}/api/:path*`,
              },
            ]
          : [],
    };
  },
};
export default config;
