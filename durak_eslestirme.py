import re
import unicodedata
from collections import defaultdict


ESDEGERLER = {
    "cad": "cadde",
    "cd": "cadde",
    "caddesi": "cadde",
    "sk": "sokak",
    "sok": "sokak",
    "sokagi": "sokak",
    "mh": "mahalle",
    "mah": "mahalle",
    "mahallesi": "mahalle",
    "blv": "bulvar",
    "bulvari": "bulvar",
    "pk": "park",
    "lis": "lisesi",
    "jand": "jandarma",
    "yrd": "yurdu",
    "ilkok": "ilkokulu",
    "ilkokul": "ilkokulu",
    "ibni": "ibn i",
}

DURAK_SOZCUKLERI = {
    "durak",
    "duragi",
    "duragina",
    "duragindan",
    "duraginda",
    "duragini",
    "duraginin",
}


def eslestirme_metni(metin):
    if not metin:
        return ""

    metin = re.sub(
        r"^\s*\d{4,}\s*[-–]\s*",
        "",
        str(metin),
    )
    metin = metin.casefold().replace("ı", "i")
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(
        c for c in metin
        if not unicodedata.combining(c)
    )
    metin = re.sub(r"[^a-z0-9]+", " ", metin)

    return " ".join(
        ESDEGERLER.get(k, k)
        for k in metin.split()
        if k not in DURAK_SOZCUKLERI
    )


def harf_uzakligi(a, b):
    tablo = [list(range(len(b) + 1))]

    for i, x in enumerate(a, 1):
        satir = [i]

        for j, y in enumerate(b, 1):
            deger = min(
                tablo[i - 1][j] + 1,
                satir[j - 1] + 1,
                tablo[i - 1][j - 1] + (x != y),
            )

            if (
                i > 1
                and j > 1
                and x == b[j - 2]
                and a[i - 2] == y
            ):
                deger = min(
                    deger,
                    tablo[i - 2][j - 2] + 1,
                )

            satir.append(deger)

        tablo.append(satir)

    return tablo[-1][-1]


def kelime_maliyeti(aranan, aday):
    if aranan == aday:
        return 0

     
    if any(c.isdigit() for c in aranan + aday):
        return None

    
    if min(len(aranan), len(aday)) < 4:
        return None

    bicimler = {aday}
    bicimler.update(
        k for k, v in ESDEGERLER.items()
        if v == aday
    )

    maliyet = min(
        harf_uzakligi(aranan, bicim)
        for bicim in bicimler
    )

    sinir = (
        2
        if min(len(aranan), len(aday)) >= 9
        else 1
    )

    return maliyet if maliyet <= sinir else None


def benzerlik_maliyeti(aranan, aday):
    if re.findall(r"\d+", aranan) != re.findall(r"\d+", aday):
        return None

    a = aranan.split()
    b = aday.split()

    if len(a) != len(b):
        return None

    toplam = 0

    for x, y in zip(a, b):
        maliyet = kelime_maliyeti(x, y)

        if maliyet is None:
            return None

        toplam += maliyet

    return toplam if toplam <= 2 else None


def kayitlarda_ara(yer_adi, satirlar):
    kod = re.fullmatch(
        r"\s*(\d{5})(?:\s+kodlu\b.*)?\s*",
        str(yer_adi or ""),
        re.IGNORECASE,
    )

    if kod:
        return [
            s for s in satirlar
            if str(s[0]) == kod.group(1)
        ]

    aranan = eslestirme_metni(yer_adi)

    if not aranan:
        return []

    gruplar = defaultdict(list)

    for satir in satirlar:
        gruplar[
            eslestirme_metni(satir[1])
        ].append(satir)

    
    if aranan in gruplar:
        return list(gruplar[aranan])

    sayilar = re.findall(r"\d+", aranan)

    adaylar = {
        ad: kayitlar
        for ad, kayitlar in gruplar.items()
        if (
            not sayilar
            or re.findall(r"\d+", ad) == sayilar
        )
    }

    bosluksuz = aranan.replace(" ", "")

    ayni = [
        ad for ad in adaylar
        if ad.replace(" ", "") == bosluksuz
    ]

    if len(ayni) == 1:
        return list(adaylar[ayni[0]])

    if len(ayni) > 1:
        return []

    
    kosullar = (
        lambda ad: ad.startswith(aranan + " "),
        lambda ad: (
            " " + aranan + " "
            in " " + ad + " "
        ),
    )

    for kosul in kosullar:
        bulunan = [
            satir
            for ad, kayitlar in adaylar.items()
            if kosul(ad)
            for satir in kayitlar
        ]

        if bulunan:
            return bulunan

    yakinlar = []

    for ad in adaylar:
        maliyet = benzerlik_maliyeti(aranan, ad)

        if maliyet is not None:
            yakinlar.append((maliyet, ad))

    yakinlar.sort()

    if not yakinlar:
        return []

    
    if (
        len(yakinlar) > 1
        and yakinlar[1][0] - yakinlar[0][0] < 2
    ):
        return []

    return list(adaylar[yakinlar[0][1]])


def durak_ara(yer_adi):
    from db import baglanti_ac

    if not eslestirme_metni(yer_adi):
        return []

    with baglanti_ac() as baglanti:
        satirlar = baglanti.execute(
            """
            SELECT
                durak_kodu,
                durak_adi,
                enlem,
                boylam
            FROM duraklar
            ORDER BY durak_adi, durak_kodu
            """
        ).fetchall()

    return kayitlarda_ara(yer_adi, satirlar)


def durak_adi_oner(yer_adi, satirlar):
    aranan = eslestirme_metni(yer_adi)
    sayilar = re.findall(r"\d+", aranan)
    eslesenler = []

    for satir in satirlar:
        ad = eslestirme_metni(satir[1])
        kelimeler = ad.split()

        if not kelimeler:
            continue

        if len(kelimeler) == 1 and len(ad) < 5:
            continue

        if re.findall(r"\d+", ad) != sayilar:
            continue

        if aranan.endswith(" " + ad):
            eslesenler.append(
                (len(kelimeler), len(ad), ad, satir)
            )

    if not eslesenler:
        return []

    en_iyi = max(
        (s[0], s[1])
        for s in eslesenler
    )

    secilen = [
        s for s in eslesenler
        if (s[0], s[1]) == en_iyi
    ]

    if len({s[2] for s in secilen}) != 1:
        return []

    return [s[3] for s in secilen]


def durak_oner(yer_adi):
    from db import baglanti_ac

    with baglanti_ac() as baglanti:
        satirlar = baglanti.execute(
            """
            SELECT durak_kodu, durak_adi, enlem, boylam
            FROM duraklar
            ORDER BY durak_adi, durak_kodu
            """
        ).fetchall()

    return durak_adi_oner(yer_adi, satirlar)