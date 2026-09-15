const nextConfig = {
  reactStrictMode: true,
  // Für das produktive Docker-Image: Next.js bündelt einen eigenständigen
  // Node-Server samt benötigter node_modules unter .next/standalone, sodass
  // die Runner-Stage kein npm install mehr braucht.
  output: "standalone",
};

export default nextConfig;
