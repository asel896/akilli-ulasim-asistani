import argparse
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


TABLOLAR = {
    "duraklar": ("durak_kodu", "durak_adi", "enlem", "boylam"),
    "hatlar": ("hat_kodu", "hat_adi", "hizmet_turu"),
    "hat_duraklar": ("hat_kodu", "yon", "sira", "durak_kodu"),
    "guzergahlar": ("guzergah_id", "hat_kodu", "kaynak_yon"),
    "guzergah_noktalari": ("guzergah_id", "sira", "enlem", "boylam"),
}


def veritabanindan_oku():
    from db import baglanti_ac

    veri = {}
    with baglanti_ac() as baglanti:
        try:
            with baglanti.cursor() as imlec:
                imlec.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                imlec.execute("SHOW transaction_read_only")
                if imlec.fetchone()[0] != "on":
                    raise RuntimeError("Salt okunur işlem doğrulanamadı.")
                imlec.execute("SET LOCAL statement_timeout = '60s'")
                for tablo, alanlar in TABLOLAR.items():
                    imlec.execute(
                        f"SELECT {', '.join(alanlar)} FROM public.{tablo}"
                    )
                    veri[tablo] = [
                        dict(zip(alanlar, satir))
                        for satir in imlec.fetchall()
                    ]
        finally:
            baglanti.rollback()
    return veri


def yedekten_oku(dosya):
    veri = {tablo: [] for tablo in TABLOLAR}
    gorulen = set()
    tablo = None
    alanlar = []
    desen = re.compile(r"COPY public\.(\w+) \(([^)]+)\) FROM stdin;")

    with Path(dosya).open(encoding="utf-8-sig") as kaynak:
        for satir in kaynak:
            if tablo is None:
                eslesme = desen.fullmatch(satir.rstrip("\r\n"))
                if eslesme and eslesme[1] in TABLOLAR:
                    tablo = eslesme[1]
                    alanlar = [a.strip() for a in eslesme[2].split(",")]
                    if not set(TABLOLAR[tablo]) <= set(alanlar):
                        raise ValueError(f"Yedekte beklenen sütunlar eksik: {tablo}")
                    gorulen.add(tablo)
                continue

            if satir.rstrip("\r\n") == "\\.":
                tablo = None
                continue

            degerler = satir.rstrip("\r\n").split("\t")
            if len(degerler) != len(alanlar):
                raise ValueError(f"Yedekte geçersiz COPY satırı: {tablo}")
            veri[tablo].append(dict(zip(
                alanlar,
                [None if d == r"\N" else d for d in degerler],
            )))

    if tablo is not None:
        raise ValueError("Yedekte tamamlanmamış COPY bölümü var.")
    if gorulen != set(TABLOLAR):
        raise ValueError("Yedekte eksik tablolar: " + ", ".join(set(TABLOLAR) - gorulen))
    return veri


def koordinat_gecerli(satir):
    try:
        lat, lon = float(satir["enlem"]), float(satir["boylam"])
        return (
            math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180
            and (lat != 0 or lon != 0)
        )
    except (TypeError, ValueError, OverflowError):
        return False


def sira_degeri(deger):
    try:
        sayi = int(deger)
        if sayi < 1 or str(sayi) != str(deger):
            return None
        return sayi
    except (TypeError, ValueError, OverflowError):
        return None


def kontrol(veri, motoru_kontrol_et=True):
    hatalar = defaultdict(list)
    uyarilar = defaultdict(list)
    hatlar = {str(h["hat_kodu"]): h for h in veri["hatlar"]}
    duraklar = {str(d["durak_kodu"]): d for d in veri["duraklar"]}
    geometriler = {str(g["guzergah_id"]): g for g in veri["guzergahlar"]}

    for tablo in TABLOLAR:
        if not veri[tablo]:
            hatalar["Boş tablo"].append(tablo)

    for tablo, alan in (
        ("hatlar", "hat_kodu"),
        ("duraklar", "durak_kodu"),
        ("guzergahlar", "guzergah_id"),
    ):
        sayac = Counter(str(s[alan]) for s in veri[tablo])
        for kimlik, adet in sayac.items():
            if adet > 1:
                hatalar["Tekrarlanan kimlik"].append(f"{tablo}: {kimlik}")

    for kod, durak in duraklar.items():
        if not kod.strip() or not str(durak.get("durak_adi") or "").strip():
            hatalar["Boş durak adı/kodu"].append(kod)
        if not koordinat_gecerli(durak):
            hatalar["Geçersiz durak koordinatı"].append(kod)

    for kod, hat in hatlar.items():
        if not kod.strip() or not str(hat.get("hat_adi") or "").strip():
            hatalar["Boş hat adı/kodu"].append(kod)

    yollar = defaultdict(list)
    kullanilan = set()
    for satir in veri["hat_duraklar"]:
        hat, kod = str(satir["hat_kodu"]), str(satir["durak_kodu"])
        yon = satir["yon"]
        sira = sira_degeri(satir["sira"])
        etiket = f"{hat}/{yon}/{satir['sira']}/{kod}"
        if hat not in hatlar:
            hatalar["Olmayan hatta durak bağlantısı"].append(etiket)
        if kod not in duraklar:
            hatalar["Olmayan durağa bağlantı"].append(etiket)
        if yon not in ("gidis", "donus"):
            hatalar["Geçersiz yön"].append(etiket)
        if sira is None:
            hatalar["Geçersiz durak sırası"].append(etiket)
        else:
            yollar[(hat, yon)].append((sira, kod))
        kullanilan.add(kod)

    def siralari_kontrol_et(etiket, siralar):
        siralar = sorted(siralar)
        if len(siralar) != len(set(siralar)):
            hatalar["Tekrarlanan sıra"].append(etiket)
        if siralar != list(range(1, len(siralar) + 1)):
            hatalar["Eksik veya kesintili sıra"].append(etiket)

    for (hat, yon), yol in yollar.items():
        yol.sort()
        siralari_kontrol_et(f"Duraklar: {hat}/{yon}", [s for s, _ in yol])
        if len(yol) < 2:
            uyarilar["İkiden az durak içeren hat/yön"].append(f"{hat}/{yon}")

    for kod in hatlar:
        if not any(h == kod for h, _ in yollar):
            hatalar["Durağı olmayan hat"].append(kod)
    for kod in sorted(set(duraklar) - kullanilan):
        uyarilar["Hiçbir hatta bağlı olmayan durak"].append(kod)

    nokta_siralari = defaultdict(list)
    for satir in veri["guzergah_noktalari"]:
        kimlik = str(satir["guzergah_id"])
        if kimlik not in geometriler:
            hatalar["Olmayan güzergâha nokta bağlantısı"].append(kimlik)
        if not koordinat_gecerli(satir):
            hatalar["Geçersiz güzergâh koordinatı"].append(f"{kimlik}/{satir['sira']}")
        sira = sira_degeri(satir["sira"])
        if sira is None:
            hatalar["Geçersiz güzergâh sırası"].append(f"{kimlik}/{satir['sira']}")
        else:
            nokta_siralari[kimlik].append(sira)

    for kimlik, geometri in geometriler.items():
        if str(geometri["hat_kodu"]) not in hatlar:
            hatalar["Olmayan hatta güzergâh bağlantısı"].append(kimlik)
        siralar = nokta_siralari[kimlik]
        if len(siralar) < 2:
            hatalar["İkiden az noktalı güzergâh"].append(kimlik)
        if siralar:
            siralari_kontrol_et(f"Güzergâh: {kimlik}", siralar)

    deneme_sayisi = 0
    if motoru_kontrol_et and not hatalar:
        from rota_motoru import hesapla

        for (hat, yon), yol in sorted(yollar.items()):
            kayitlar = [
                (hat, hatlar[hat]["hat_adi"], yon, sira, kod,
                 float(duraklar[kod]["enlem"]), float(duraklar[kod]["boylam"]))
                for sira, kod in yol
            ]
            denemeler = {(yol[0][1], yol[-1][1]), (yol[-1][1], yol[0][1])}
            denemeler.update((a[1], b[1]) for a, b in zip(yol, yol[1:]))
            for bas, son in sorted(denemeler):
                if bas == son:
                    continue
                deneme_sayisi += 1
                beklenen = any(
                    s1 < s2
                    for s1, k1 in yol if k1 == bas
                    for s2, k2 in yol if k2 == son
                )
                def aday(kod):
                    return {**duraklar[kod], "durak_kodu": kod, "mesafe_metre": None}
                try:
                    cevap = hesapla([aday(bas)], [aday(son)], kayitlar)
                    uygun = (
                        isinstance(cevap, dict)
                        and cevap.get("basarili") == beklenen
                        and (not beklenen or cevap.get("sonuc_turu") == "dogrudan")
                    )
                    if not uygun:
                        hatalar["Rota motoru sıra sonucu uyuşmazlığı"].append(f"{hat}/{yon}: {bas} -> {son}")
                except Exception as hata:
                    hatalar["Rota motoru çalışma hatası"].append(f"{hat}/{yon}: {type(hata).__name__}: {hata}")

    bos_yonler = [
        f"{hat}/{yon}"
        for hat in sorted(hatlar)
        for yon in ("gidis", "donus")
        if (hat, yon) not in yollar
    ]
    return hatalar, uyarilar, deneme_sayisi, bos_yonler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql-yedegi")
    parser.add_argument("--sadece-veri", action="store_true")
    args = parser.parse_args()
    try:
        veri = yedekten_oku(args.sql_yedegi) if args.sql_yedegi else veritabanindan_oku()
        hatalar, uyarilar, denemeler, bos_yonler = kontrol(veri, not args.sadece_veri)
    except Exception as hata:
        print(f"KONTROL TAMAMLANAMADI: {type(hata).__name__}: {hata}")
        return 2

    print("AKILLI ULAŞIM VERİ VE ROTA KONTROLÜ")
    print("Kaynak:", "SQL yedeği" if args.sql_yedegi else "Salt okunur veritabanı işlemi")
    for tablo, satirlar in veri.items():
        print(f"{tablo}: {len(satirlar)} kayıt")
    print(f"Gerçek durak sıralarıyla motor denemesi: {denemeler}")
    print(f"Durak listesi olmayan yön: {len(bos_yonler)}")
    print("Boş yön tek başına hata sayılmaz; ring hatlarda dönüş listesi boş olabilir.")
    for baslik, gruplar in (("HATA", hatalar), ("UYARI", uyarilar)):
        print(f"\n{baslik} sayısı: {sum(map(len, gruplar.values()))}")
        for tur, ornekler in sorted(gruplar.items()):
            print(f"  {tur}: {len(ornekler)}")
            for ornek in ornekler[:8]:
                print(f"    {ornek}")
            if len(ornekler) > 8:
                print(f"    ... {len(ornekler) - 8} kayıt daha")
    if not args.sadece_veri and hatalar and denemeler == 0:
        print("Veri hataları nedeniyle motor denemeleri çalıştırılmadı.")
    print("\nSONUÇ:", "HATA BULUNDU" if hatalar else "Kontrol edilen kurallarda hata bulunmadı.")
    print("Bu kontrol, verilerin güncel MOTAŞ hizmetiyle aynı olduğunu kanıtlamaz.")
    print("Sefer uyumu, yürünebilirlik ve bütün durak çiftlerinin en iyi rotası test edilmez.")
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
