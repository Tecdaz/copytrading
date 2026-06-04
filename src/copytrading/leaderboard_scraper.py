"""Scraper for Polymarket leaderboard."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


@dataclass
class LeaderboardEntry:
    """Entry from Polymarket leaderboard."""

    address: str
    username: str
    pnl: float
    volume: float
    rank: int = 0
    profile_url: str = ""
    x_username: str = ""
    verified_badge: bool = False
    profile_image: str = ""


class PolymarketLeaderboardScraper:
    """Scrapes the Polymarket leaderboard from the website."""

    BASE_URL = "https://polymarket.com/leaderboard"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def fetch_weekly_top(self, limit: int = 20) -> list[LeaderboardEntry]:
        """Fetch the weekly leaderboard (top traders by PnL)."""
        # The leaderboard page is server-rendered, so we can fetch it directly
        response = httpx.get(self.BASE_URL, timeout=self.timeout)
        response.raise_for_status()

        html = response.text
        return self._parse_leaderboard(html, limit)

    def _parse_leaderboard(self, html: str, limit: int) -> list[LeaderboardEntry]:
        """Parse leaderboard entries from HTML."""
        entries: list[LeaderboardEntry] = []

        # The HTML structure has entries like:
        # [username](/profile/0xaddress)
        # +$1,064,165
        # $4,874,769

        # Extract all profile links with wallet addresses
        profile_pattern = r"/profile/(0x[a-fA-F0-9]{40})"
        all_addresses = re.findall(profile_pattern, html)

        # Deduplicate addresses while preserving order
        seen_addresses: set[str] = set()
        unique_addresses: list[str] = []
        for addr in all_addresses:
            addr_lower = addr.lower()
            if addr_lower not in seen_addresses:
                seen_addresses.add(addr_lower)
                unique_addresses.append(addr_lower)

        # Extract usernames - they appear as link text before the profile URL
        # Pattern: [username](/profile/0x...)
        username_pattern = r"\[([^\]]+)\]\(/profile/0x[a-fA-F0-9]{40}\)"
        all_usernames = re.findall(username_pattern, html)

        # Deduplicate usernames in same order as addresses
        seen_usernames: set[str] = set()
        unique_usernames: list[str] = []
        for username in all_usernames:
            if username not in seen_usernames:
                seen_usernames.add(username)
                unique_usernames.append(username)

        # Extract PnL values (format: +$1,064,165)
        pnl_pattern = r"\+\$([0-9,]+)"
        pnl_values = re.findall(pnl_pattern, html)

        # Extract volume values (format: $4,874,769 without +)
        # We need to be careful to only get the volume values that follow PnL
        # Looking at the pattern: +$PnL followed by $Volume
        volume_pattern = r"\+\$[0-9,]+\s*\n?\s*\$([0-9,]+)"
        volume_values = re.findall(volume_pattern, html)

        # If volume pattern didn't work, try extracting all non-PnL dollar values
        if not volume_values:
            all_dollars = re.findall(r"\$([0-9,]+)", html)
            # Every other value starting from index 1 should be volume
            volume_values = all_dollars[1::2][: len(pnl_values)]

        # Build entries
        for i in range(min(limit, len(unique_addresses))):
            address = unique_addresses[i]

            username = unique_usernames[i] if i < len(unique_usernames) else f"{address[:10]}..."

            pnl = 0.0
            if i < len(pnl_values):
                pnl_str = pnl_values[i].replace(",", "")
                pnl = float(pnl_str)

            volume = 0.0
            if i < len(volume_values):
                volume_str = volume_values[i].replace(",", "")
                volume = float(volume_str)

            entries.append(
                LeaderboardEntry(
                    rank=i + 1,
                    address=address,
                    username=username,
                    pnl=pnl,
                    volume=volume,
                    profile_url=f"https://polymarket.com/profile/{address}",
                )
            )

        return entries


def main() -> None:
    """Test the scraper."""
    scraper = PolymarketLeaderboardScraper()
    entries = scraper.fetch_weekly_top(20)

    print(f"Found {len(entries)} leaderboard entries:\n")
    for entry in entries:
        print(
            f"{entry.rank:2d}. {entry.username:30s} "
            f"PnL: +${entry.pnl:>12,.2f}  "
            f"Volume: ${entry.volume:>12,.2f}  "
            f"Address: {entry.address}"
        )


if __name__ == "__main__":
    main()
