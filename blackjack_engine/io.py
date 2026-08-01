from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
    "shoe_id",
    "hand_index",
    "seed",
    "player_position",
    "hand_position",
    "player_cards",
    "dealer_upcard",
    "dealer_final_cards",
    "actions",
    "bet_cents",
    "insurance_bet_cents",
    "outcome",
    "net_profit_cents",
    "shoe_remaining_cards_before_hand",
]


def append_hand_results_csv(path: str | Path, settlements: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output.exists()

    with output.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for row in settlements:
            csv_row = {key: row.get(key) for key in CSV_COLUMNS}
            csv_row["player_cards"] = " ".join(row.get("player_cards", []))
            csv_row["dealer_final_cards"] = " ".join(row.get("dealer_final_cards", []))
            csv_row["actions"] = ",".join(row.get("actions", []))
            writer.writerow(csv_row)
