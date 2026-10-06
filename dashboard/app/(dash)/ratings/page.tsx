import RatingsView from "@/components/RatingsView";
import { PageHeader } from "@/components/ui";
import { loadDashboard } from "@/lib/data";

export default function RatingsPage() {
  const d = loadDashboard();
  return (
    <>
      <PageHeader eyebrow="Elo, rebuilt every morning" title="Ratings" />
      <RatingsView epl={d.eplRatings} atp={d.atpRatings} />
    </>
  );
}
