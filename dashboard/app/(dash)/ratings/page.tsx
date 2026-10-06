import RatingsView from "@/components/RatingsView";
import { PageHeader } from "@/components/ui";
import { loadDashboard } from "@/lib/data";
import { loadRatings } from "@/lib/ratings";

export default function RatingsPage() {
  const d = loadDashboard();
  const surfaces = Object.fromEntries(
    d.atpRatings.map((r) => [r.player, { hard: r.elo_hard, clay: r.elo_clay, grass: r.elo_grass }]),
  );
  return (
    <>
      <PageHeader eyebrow="Elo, rebuilt every morning" title="Ratings" />
      <RatingsView data={loadRatings()} surfaces={surfaces} />
    </>
  );
}
