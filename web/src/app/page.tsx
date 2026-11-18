"use client";

import { useEffect, useState } from "react";
import { API_URL, LOCAL_SERVICES } from "@/lib/api";

type Ready = {
  status?: string;
  database?: string;
  storage?: string;
  model?: string;
  detail?: string;
};

type CheckState = { state: "memeriksa" | "siap" | "belum" | "mati"; data?: Ready };

const PAGES = [
  { href: "/input", label: "Input Data Harian" },
  { href: "/prediksi", label: "Prediksi 7 Hari" },
  { href: "/simulasi", label: "Simulasi Porsi" },
  { href: "/insight", label: "Insight & Penyebab" },
  { href: "/laporan", label: "Laporan" },
];

export default function Home() {
  const [check, setCheck] = useState<CheckState>({ state: "memeriksa" });

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`${API_URL}/health/ready`, { cache: "no-store" });
        const data: Ready = await response.json();
        if (active) setCheck({ state: response.ok ? "siap" : "belum", data });
      } catch {
        if (active) setCheck({ state: "mati" });
      }
    }
    load();
    const timer = setInterval(load, 10000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const badge = {
    memeriksa: "bg-zinc-200 text-zinc-700",
    siap: "bg-emerald-100 text-emerald-800",
    belum: "bg-amber-100 text-amber-800",
    mati: "bg-red-100 text-red-800",
  }[check.state];
  const message = {
    memeriksa: "Memeriksa API...",
    siap: "Sistem siap dipakai",
    belum: check.data?.detail ?? "API menyala, sistem belum siap",
    mati: "API tidak dapat dihubungi. Jalankan docker compose up -d di folder proyek.",
  }[check.state];

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-semibold">FoodSave</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">
        Rilis lokal di laptop ini (localhost). Prediksi limbah makanan restoran.
      </p>

      <section className="mt-8 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-medium">Status sistem</h2>
          <span className={`rounded px-2 py-1 text-sm ${badge}`}>{message}</span>
        </div>
        {check.data && check.state === "siap" && (
          <dl className="mt-4 grid grid-cols-[10rem_1fr] gap-y-1 text-sm">
            <dt className="text-zinc-500">Database</dt>
            <dd>{check.data.database}</dd>
            <dt className="text-zinc-500">Penyimpanan model</dt>
            <dd>{check.data.storage === "hdfs" ? "Hadoop HDFS" : check.data.storage}</dd>
            <dt className="text-zinc-500">Model aktif</dt>
            <dd className="font-mono">{check.data.model}</dd>
          </dl>
        )}
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Layanan lokal</h2>
        <ul className="mt-3 divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {LOCAL_SERVICES.map((service) => (
            <li key={service.url} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <p className="font-medium">{service.label}</p>
                <p className="text-sm text-zinc-500">{service.note}</p>
              </div>
              <a className="text-sm text-emerald-700 underline dark:text-emerald-400" href={service.url}
                 target="_blank" rel="noreferrer">
                {service.url.replace("http://", "")}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-medium">Halaman aplikasi</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Kerangka halaman; belum terhubung ke API.
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {PAGES.map((page) => (
            <li key={page.href}>
              <a href={page.href}
                 className="block rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900">
                {page.label}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
