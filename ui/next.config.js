/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow external packages to be bundled
  transpilePackages: ["copilotkit-langgraph-history"],
};

module.exports = nextConfig;


