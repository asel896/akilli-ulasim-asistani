import math
from collections import defaultdict
from itertools import product

from shapely.errors import GEOSException
from shapely.geometry import Point, shape


def mesafe(a, b):
    x, y = math.radians(a[0]), math.radians(b[0])
    dx = y - x
    dy = math.radians(b[1] - a[1])
    z = (
        math.sin(dx / 2) ** 2
        + math.cos(x) * math.cos(y) * math.sin(dy / 2) ** 2
    )
    return 12742017.6 * math.asin(
        math.sqrt(min(1, max(0, z)))
    )


def alan_oku(veri):
    if (
        not isinstance(veri, dict)
        or veri.get("type") not in ("Polygon", "MultiPolygon")
    ):
        return None

    try:
        alan = shape(veri)
        x1, y1, x2, y2 = alan.bounds

        if (
            alan.is_empty
            or not alan.is_valid
            or not all(math.isfinite(v) for v in alan.bounds)
            or not (
                -180 <= x1 <= x2 <= 180
                and -90 <= y1 <= y2 <= 90
            )
        ):
            return None

        return alan
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        GEOSException,
    ):
        return None


def adaylari_bul(konum, duraklar, yaricap):
    if konum.get("cozum_turu") == "durak_eslesmesi":
        return [
            {
                **d,
                "durak_kodu": str(d["durak_kodu"]),
                "mesafe_metre": None,
            }
            for d in konum.get("durak_eslesmeleri", [])
        ]

    koordinat = konum.get("adres_koordinati") or {}

    if (
        konum.get("cozum_turu") != "geocoding"
        or not koordinat
    ):
        return []

    alan = alan_oku(koordinat.get("alan_geojson"))
    bulunan = []

    for kod, ad, lat, lon in duraklar:
        if lat is None or lon is None:
            continue

        lat, lon = float(lat), float(lon)

        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            continue

        if alan is not None:
            if not alan.covers(Point(lon, lat)):
                continue

            # Alan içinde olmak belirli binaya
            # sıfır metre uzaklıkta olmak değildir.
            uzaklik = None
        else:
            uzaklik = mesafe(
                (
                    koordinat["enlem"],
                    koordinat["boylam"],
                ),
                (lat, lon),
            )

            if uzaklik > yaricap:
                continue

        bulunan.append(
            {
                "durak_kodu": str(kod),
                "durak_adi": ad,
                "enlem": lat,
                "boylam": lon,
                "mesafe_metre": uzaklik,
                "alan_icinde": alan is not None,
            }
        )

    if alan is not None and not bulunan:
        return adaylari_bul(
            {
                **konum,
                "adres_koordinati": {
                    **koordinat,
                    "alan_geojson": None,
                },
            },
            duraklar,
            yaricap,
        )

    return bulunan


def hesapla(
    baslangic,
    hedef,
    kayitlar,
    limit=5,
    aktarma_limiti=150,
):
    bas = {
        str(d["durak_kodu"]): d
        for d in baslangic
    }
    bit = {
        str(d["durak_kodu"]): d
        for d in hedef
    }

    yollar = defaultdict(list)

    for hat, ad, yon, sira, kod, lat, lon in kayitlar:
        yollar[(hat, ad, yon)].append(
            (int(sira), str(kod), lat, lon)
        )

    for yol in yollar.values():
        yol.sort(key=lambda d: (d[0], d[1]))

    def erisim(d):
        
        return float(d.get("mesafe_metre") or 0)

    def durak(d):
        d = dict(d)

        if d.get("mesafe_metre") is not None:
            d["mesafe_metre"] = round(
                float(d["mesafe_metre"]), 2
            )

        return d

    def toplam(b, i, aktarma=0):
        if (
            b.get("mesafe_metre") is None
            or i.get("mesafe_metre") is None
        ):
            return None

        return round(
            erisim(b) + erisim(i) + aktarma, 2
        )

    def sonuc(tur, bulunan):
        sirali = sorted(
            bulunan.values(),
            key=lambda d: (d[0], str(d[1])),
        )

        if not sirali:
            mesaj = (
                "Belirlenen erişim alanlarında doğrudan "
                "veya tek aktarmalı rota bulunamadı."
            )
        elif tur == "dogrudan":
            mesaj = "Doğrudan hat bulundu."
        else:
            mesaj = "Tek aktarmalı seçenek bulundu."

        return {
            "basarili": bool(sirali),
            "sonuc_turu": tur if sirali else None,
            "bulunan_secenek_sayisi": len(sirali),
            "secenekler": [
                d[1] for d in sirali[:limit]
            ],
            "mesaj": mesaj,
            "bilgi": (
                "Tüm erişim adayları değerlendirilir; "
                "önce doğrudan hat aranır. Aynı hat/yön "
                "için bir seçenek gösterilir. Sıralama "
                "bilinen kuş uçuşu erişim ve aktarma "
                "mesafesi, ardından durak aralığıdır. "
                "Alan içindeki duraklarda bina uzaklığı "
                "bilinmez. Sefer saatleri, yürünebilirlik "
                "ve en hızlı rota hesaplanmaz."
            ),
        }

    dogrudan = {}

    for (hat, ad, yon), yol in yollar.items():
        for b in yol:
            if b[1] not in bas:
                continue

            for i in yol:
                if (
                    i[1] not in bit
                    or b[0] >= i[0]
                    or b[1] == i[1]
                ):
                    continue

                bd, id_ = bas[b[1]], bit[i[1]]

                skor = (
                    erisim(bd) + erisim(id_),
                    i[0] - b[0],
                    b[1],
                    i[1],
                    b[0],
                    i[0],
                )

                secenek = {
                    "hat_kodu": hat,
                    "hat_adi": ad,
                    "yon": yon,
                    "binis_duragi": durak(bd),
                    "inis_duragi": durak(id_),
                    "binis_sirasi": b[0],
                    "inis_sirasi": i[0],
                    "durak_araligi": i[0] - b[0],
                    "toplam_erisim_mesafesi_metre": toplam(
                        bd, id_
                    ),
                }

                anahtar = (hat, yon)

                if (
                    anahtar not in dogrudan
                    or skor < dogrudan[anahtar][0]
                ):
                    dogrudan[anahtar] = (
                        skor,
                        secenek,
                    )

    if dogrudan:
        for _, secenek in dogrudan.values():
            yol = yollar[
                (
                    secenek["hat_kodu"],
                    secenek["hat_adi"],
                    secenek["yon"],
                )
            ]

            alternatifler = {}

            for i in yol:
                if (
                    i[1] in bit
                    and i[0] > secenek["binis_sirasi"]
                    and i[1]
                    != secenek["binis_duragi"]["durak_kodu"]
                ):
                    alternatifler.setdefault(
                        i[1],
                        {
                            **durak(bit[i[1]]),
                            "inis_sirasi": i[0],
                        },
                    )

            secenek["uygun_inis_duraklari"] = list(
                alternatifler.values()
            )

        return _durak_alternatiflerini_ekle(
            sonuc("dogrudan", dogrudan),
            bas,
            bit,
            yollar,
        )

    if not bas or not bit:
        return sonuc(None, {})

    ilk = defaultdict(dict)
    ikinci = defaultdict(dict)

    def ekle(sozluk, kod, anahtar, skor, veri):
        onceki = sozluk[kod].get(anahtar)

        if onceki is None or skor < onceki[0]:
            sozluk[kod][anahtar] = (skor, veri)

    noktalar = {}

    for anahtar, yol in yollar.items():
        for t in yol:
            if t[2] is None or t[3] is None:
                continue

            lat, lon = float(t[2]), float(t[3])

            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                continue

            noktalar[t[1]] = (lat, lon)

            for b in yol:
                if b[1] in bas and b[0] < t[0]:
                    skor = (
                        erisim(bas[b[1]]),
                        t[0] - b[0],
                        b[1],
                        b[0],
                        t[0],
                    )

                    ekle(
                        ilk,
                        t[1],
                        (*anahtar, b[1]),
                        skor,
                        (b, t),
                    )

            for i in yol:
                if i[1] in bit and t[0] < i[0]:
                    skor = (
                        erisim(bit[i[1]]),
                        i[0] - t[0],
                        i[1],
                        t[0],
                        i[0],
                    )

                    ekle(
                        ikinci,
                        t[1],
                        (*anahtar, i[1]),
                        skor,
                        (t, i),
                    )

    def hucre(nokta):
        lat, lon = map(math.radians, nokta)
        r = 6371008.8 / aktarma_limiti

        return tuple(
            math.floor(v * r)
            for v in (
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
            )
        )

    grid = defaultdict(list)

    for kod in ikinci:
        grid[hucre(noktalar[kod])].append(kod)

    bulunan = {}

    def hat_verisi(a, bini, ini):
        return {
            "hat_kodu": a[0],
            "hat_adi": a[1],
            "yon": a[2],
            "binis_sirasi": bini,
            "inis_sirasi": ini,
        }

    for k1, ilk_hatlar in ilk.items():
        h = hucre(noktalar[k1])

        for ofset in product((-1, 0, 1), repeat=3):
            komsu = tuple(
                h[j] + ofset[j]
                for j in range(3)
            )

            for k2 in grid.get(komsu, []):
                uzaklik = mesafe(
                    noktalar[k1],
                    noktalar[k2],
                )

                if uzaklik > aktarma_limiti:
                    continue

                for a1, (_, (b, t1)) in ilk_hatlar.items():
                    for a2, (_, (t2, i)) in ikinci[k2].items():
                        if (
                            a1[0] == a2[0]
                            or b[1] == i[1]
                        ):
                            continue

                        bd, id_ = bas[b[1]], bit[i[1]]

                        aralik = (
                            t1[0] - b[0]
                            + i[0] - t2[0]
                        )

                        skor = (
                            erisim(bd) + erisim(id_) + uzaklik,
                            aralik,
                            k1,
                            k2,
                            b[1],
                            i[1],
                            b[0],
                            t1[0],
                            t2[0],
                            i[0],
                        )

                        anahtar = (
                            a1[0],
                            a1[2],
                            a2[0],
                            a2[2],
                        )

                        if (
                            anahtar in bulunan
                            and bulunan[anahtar][0] <= skor
                        ):
                            continue

                        bulunan[anahtar] = (
                            skor,
                            {
                                "binis_duragi": durak(bd),
                                "inis_duragi": durak(id_),
                                "birinci_hat": hat_verisi(
                                    a1, b[0], t1[0]
                                ),
                                "ikinci_hat": hat_verisi(
                                    a2, t2[0], i[0]
                                ),
                                "aktarma": {
                                    "inilecek_durak": {
                                        "durak_kodu": k1
                                    },
                                    "binilecek_durak": {
                                        "durak_kodu": k2
                                    },
                                    "yaklasik_mesafe_metre": round(
                                        uzaklik, 2
                                    ),
                                },
                                "toplam_durak_araligi": aralik,
                                "toplam_erisim_ve_aktarma_mesafesi_metre":
                                    toplam(bd, id_, uzaklik),
                            },
                        )

    return _durak_alternatiflerini_ekle(
        sonuc("tek_aktarma", bulunan),
        bas,
        bit,
        yollar,
    )


def rota_bul(bas, hedef, limit=5):
    from rota_api import _sorgula

    kayitlar = _sorgula(
        """
        SELECT
            h.hat_kodu,
            h.hat_adi,
            hd.yon,
            hd.sira,
            hd.durak_kodu,
            d.enlem,
            d.boylam
        FROM hat_duraklar hd
        JOIN hatlar h
          ON h.hat_kodu = hd.hat_kodu
        JOIN duraklar d
          ON d.durak_kodu = hd.durak_kodu
        WHERE h.hizmet_turu IS DISTINCT FROM 'gorevli'
        ORDER BY h.hat_kodu, hd.yon, hd.sira
        """
    )

    cevap = hesapla(bas, hedef, kayitlar, limit)

    kodlar = {
        d["durak_kodu"]
        for s in cevap["secenekler"]
        for d in s.get("aktarma", {}).values()
        if isinstance(d, dict)
    }

    if kodlar:
        adlar = dict(
            _sorgula(
                """
                SELECT durak_kodu, durak_adi
                FROM duraklar
                WHERE durak_kodu = ANY(%s::varchar[])
                """,
                (list(kodlar),),
            )
        )

        for s in cevap["secenekler"]:
            for alan in (
                "inilecek_durak",
                "binilecek_durak",
            ):
                d = s["aktarma"][alan]
                d["durak_adi"] = adlar[d["durak_kodu"]]

    return cevap


def _durak_alternatiflerini_ekle(cevap, bas, bit, yollar):
    def adaylar(
        yol,
        kaynak,
        sira_alani,
        once=None,
        sonra=None,
        haric=None,
    ):
        bulunan = {}

        for sira, kod, _, _ in yol:
            if kod not in kaynak or kod == haric:
                continue

            if once is not None and sira >= once:
                continue

            if sonra is not None and sira <= sonra:
                continue

            durak = dict(kaynak[kod])
            durak["durak_kodu"] = str(kod)
            durak[sira_alani] = sira

            if durak.get("mesafe_metre") is not None:
                durak["mesafe_metre"] = round(
                    float(durak["mesafe_metre"]),
                    2,
                )

            bulunan[(kod, sira)] = durak

        return sorted(
            bulunan.values(),
            key=lambda d: (
                d[sira_alani],
                d["durak_kodu"],
            ),
        )

    for secenek in cevap["secenekler"]:
        if cevap["sonuc_turu"] == "dogrudan":
            yol = yollar[
                (
                    secenek["hat_kodu"],
                    secenek["hat_adi"],
                    secenek["yon"],
                )
            ]

            secenek["uygun_binis_duraklari"] = adaylar(
                yol,
                bas,
                "binis_sirasi",
                once=secenek["inis_sirasi"],
                haric=str(
                    secenek["inis_duragi"]["durak_kodu"]
                ),
            )

            secenek["uygun_inis_duraklari"] = adaylar(
                yol,
                bit,
                "inis_sirasi",
                sonra=secenek["binis_sirasi"],
                haric=str(
                    secenek["binis_duragi"]["durak_kodu"]
                ),
            )

        elif cevap["sonuc_turu"] == "tek_aktarma":
            ilk = secenek["birinci_hat"]
            son = secenek["ikinci_hat"]

            ilk_yol = yollar[
                (
                    ilk["hat_kodu"],
                    ilk["hat_adi"],
                    ilk["yon"],
                )
            ]

            son_yol = yollar[
                (
                    son["hat_kodu"],
                    son["hat_adi"],
                    son["yon"],
                )
            ]

            secenek["uygun_binis_duraklari"] = adaylar(
                ilk_yol,
                bas,
                "binis_sirasi",
                once=ilk["inis_sirasi"],
                haric=str(
                    secenek["inis_duragi"]["durak_kodu"]
                ),
            )

            secenek["uygun_inis_duraklari"] = adaylar(
                son_yol,
                bit,
                "inis_sirasi",
                sonra=son["binis_sirasi"],
                haric=str(
                    secenek["binis_duragi"]["durak_kodu"]
                ),
            )

    return cevap