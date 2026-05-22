/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["maplibre-gl"],
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_GEOAPI_URL: process.env.NEXT_PUBLIC_GEOAPI_URL || "http://localhost:8100",
  },
};
module.exports = nextConfig;
