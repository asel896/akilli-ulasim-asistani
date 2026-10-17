import json
from pathlib import Path

for dosya in sorted(Path("veriler").glob("*.json")):
    with open(dosya, encoding="utf-8") as kaynak:
        hat = json.load(kaynak)

    if not hat.get("arrivalStops"):
        print("\nHat:", hat.get("code"))
        print("Gidiş durak sayısı:", len(hat.get("departureStops", [])))

        varyantlar = hat.get("variants", [])

        if not varyantlar:
            print("Güzergâh varyantı yok.")

        for varyant in varyantlar:
            print(
                "Varyant:",
                varyant.get("title"),
                "| Yön:",
                varyant.get("direction"),
                "| Koordinat sayısı:",
                len(varyant.get("coordinates", []))
            )