import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  outputFileTracingRoot: path.join(import.meta.dirname, ".."),
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;