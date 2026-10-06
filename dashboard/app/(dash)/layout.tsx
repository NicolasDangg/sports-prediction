import Nav from "@/components/Nav";
import { loadDashboard } from "@/lib/data";
import { loadSearchIndex } from "@/lib/match";

export default function DashLayout({ children }: { children: React.ReactNode }) {
  const { latestDate } = loadDashboard();
  return (
    <div className="min-h-[100dvh]">
      <Nav updated={latestDate} searchIndex={loadSearchIndex()} />
      <main id="main" className="px-4 pb-28 pt-6 md:px-8 md:pt-10 lg:ml-[248px] lg:pb-14">
        <div className="mx-auto max-w-[1240px]">{children}</div>
      </main>
    </div>
  );
}
