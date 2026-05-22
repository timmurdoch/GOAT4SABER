import type { Metadata } from "next";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "AusGIS — Australian WebGIS Platform",
  description: "Spatial analysis platform for Australia",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
