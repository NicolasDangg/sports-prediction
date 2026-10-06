import BetsView from "@/components/BetsView";
import { PageHeader } from "@/components/ui";
import { loadDashboard } from "@/lib/data";

export default function BetsPage() {
  const d = loadDashboard();
  return (
    <>
      <PageHeader eyebrow="Virtual wallet ledger" title="Bets" />
      <BetsView bets={d.bets} />
    </>
  );
}
