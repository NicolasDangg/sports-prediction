"""Download historical results + bookmaker odds into data/.

EPL:    football-data.co.uk, one CSV per season (results + odds from many bookmakers,
        including *closing* odds = the final price right before kickoff).
Tennis: ATP matches 2000-now with odds from the Kaggle dataset
        "atp-tennis-2000-2023daily-pull" (updated daily; needs a free Kaggle token).
        Without a token we fall back to a public GitHub copy that stops in April 2026.
"""

import io
import os
import zipfile
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"

# Season codes look like "1213" = 2012/13. We start in 2005/06 so Elo has years
# to "warm up" before the seasons we actually evaluate on.
EPL_SEASONS = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2005, 2027)]
EPL_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
EPL_FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/dissfya/atp-tennis-2000-2023daily-pull"
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
    if not download_kaggle_atp(DATA / "tennis" / "atp_tennis.csv"):
        print("  (no Kaggle token: using the GitHub copy, which ends April 2026)")
        download(ATP_URL, DATA / "tennis" / "atp_tennis.csv")


def download_kaggle_atp(dest: Path) -> bool:
    """Kaggle accepts either a new-style API token or the classic username + key pair."""
    token = os.environ.get("KAGGLE_API_TOKEN")
    user, key = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    if not token and not (user and key):
        return False
    kwargs = {"headers": {"Authorization": f"Bearer {token}"}} if token else {"auth": (user, key)}
    resp = requests.get(KAGGLE_URL, timeout=120, **kwargs)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        dest.write_bytes(z.read("atp_tennis.csv"))
    print(f"  {dest.relative_to(DATA.parent)}  (Kaggle, {dest.stat().st_size // 1024} KB)")
    return True


if __name__ == "__main__":
    main()
