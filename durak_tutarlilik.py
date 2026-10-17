import json
from pathlib import Path

duraklar = {}
celisen_kodlar = set()

for dosya in sorted(Path("veriler").glob("*.json")):
    with open(dosya, encoding="utf-8") as kaynak:
        hat = json.load(kaynak)

    for alan in ["departureStops", "arrivalStops"]:
        for durak in hat[alan]:
            kod = str(durak["id"])

            bilgi = (
                durak["name"],
                durak["latitude"],
                durak["longitude"]
            )

            if kod not in duraklar:
                duraklar[kod] = bilgi

            elif duraklar[kod] != bilgi:
                if kod not in celisen_kodlar:
                    print("\nDurak kodu:", kod)
                    print("İlk bilgi:", duraklar[kod])
                    print("Farklı bilgi:", bilgi)
                    print("Farkın bulunduğu hat:", hat["code"])

                celisen_kodlar.add(kod)

print("\nKontrol edilen benzersiz durak:", len(duraklar))
print("Bilgileri farklılaşan durak kodu:", len(celisen_kodlar))