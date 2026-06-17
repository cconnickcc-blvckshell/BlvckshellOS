/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: {
    // The harness UI ships without an ESLint config; type-checking still runs.
    ignoreDuringBuilds: true,
  },
  env: {
    NEXT_PUBLIC_HARNESS_URL: process.env.NEXT_PUBLIC_HARNESS_URL || "http://localhost:8000",
  },
};

export default nextConfig;
