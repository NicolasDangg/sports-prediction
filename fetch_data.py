"""Download historical results + bookmaker odds into data/.

EPL:    football-data.co.uk, one CSV per season (results + odds from many bookmakers,
        including *closing* odds = the final price right before kickoff).
Tennis: ATP matches 2000-2026 with odds, from a public GitHub mirror of the
        Kaggle "atp-tennis-2000-2023daily-pull" dataset (tennis-data.co.uk went offline).
"""

from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"

# Season codes look like "1213" = 2012/13. We start in 2005/06 so Elo has years
# to "warm up" before the seasons we actually evaluate on.
EPL_SEASONS = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2005, 2027)]
EPL_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
EPL_FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
ATP_URL = "https://raw.githubusercontent.com/Mustafak50/atp-tennis-model-validation/HEAD/atp_tennis.csv"


def download(url: str, dest: Path) -> None:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  {dest.relative_to(DATA.parent)}  ({len(resp.content) // 1024} KB)")


def main() -> None:
    (DATA / "epl").mkdir(parents=True, exist_ok=True)
    (DATA / "tennis").mkdir(parents=True, exist_ok=True)

    print("EPL seasons:")
    for season in EPL_SEASONS:
        download(EPL_URL.format(season=season), DATA / "epl" / f"E0_{season}.csv")
    download(EPL_FIXTURES_URL, DATA / "epl" / "fixtures.csv")

    print("ATP:")
    download(ATP_URL, DATA / "tennis" / "atp_tennis.csv")


if __name__ == "__main__":
    main()
