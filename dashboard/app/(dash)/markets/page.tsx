import MarketsView from "@/components/MarketsView";
import { PageHeader } from "@/components/ui";
import { loadDashboard } from "@/lib/data";

export default function MarketsPage() {
  const d = loadDashboard();
  return (
    <>
      <PageHeader eyebrow={`Priced ${d.latestDate || "—"}`} title="Markets" />
      <MarketsView matches={d.upcoming} />
    </>
  );
}
