import type { Metadata } from "next";
import "./globals.css";

// Font sistem (tanpa next/font/google) agar build tidak bergantung pada internet.
export const metadata: Metadata = {
  title: "FoodSave",
  description: "Prediksi limbah makanan restoran",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
