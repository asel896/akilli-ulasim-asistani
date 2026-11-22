import re
import unicodedata
from collections import defaultdict
from db import baglanti_ac

ESDEGERLER = {
    'cad': 'cadde', 'cd': 'cadde', 'caddesi': 'cadde',
    'sk': 'sokak', 'sok': 'sokak', 'sokagi': 'sokak',
    'mh': 'mahalle', 'mah': 'mahalle', 'mahallesi': 'mahalle',
    'blv': 'bulvar', 'bulvari': 'bulvar',
    'pk': 'park', 'lis': 'lisesi', 'jand': 'jandarma',
    'yrd': 'yurdu', 'ilkok': 'ilkokulu', 'ilkokul': 'ilkokulu',
    'ibni': 'ibn i',
}
DURAK_SOZCUKLERI = {
    'durak', 'duragi', 'duragina', 'duragindan',
    'duraginda', 'duragini', 'duraginin',
}


def eslestirme_metni(metin):
    if not metin:
        return ''
    metin = re.sub(r'^\s*\d{4,}\s*[-–]\s*', '', str(metin))
    metin = metin.casefold().replace('ı', 'i')
    metin = unicodedata.normalize('NFKD', metin)
    metin = ''.join(c for c in metin if not unicodedata.combining(c))
    metin = re.sub(r'[^a-z0-9]+', ' ', metin)
    return ' '.join(
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
            if i > 1 and j > 1 and x == b[j - 2] and a[i - 2] == y:
                deger = min(deger, tablo[i - 2][j - 2] + 1)
            satir.append(deger)
        tablo.append(satir)
    return tablo[-1][-1]


def kelime_maliyeti(aranan, aday):
    if aranan == aday:
        return 0
    if any(c.isdigit() for c in aranan + aday):
        return None
    if len(aranan) < 4 or len(aday) < 4:
        return None

    bicimler = {aday}
    bicimler.update(k for k, v in ESDEGERLER.items() if v == aday)
    maliyet = min(harf_uzakligi(aranan, bicim) for bicim in bicimler)

   
    if len(aranan) >= 6 and aday.startswith(aranan):
        maliyet = min(maliyet, 1)

    sinir = 2 if min(len(aranan), len(aday)) >= 9 else 1
    return maliyet if maliyet <= sinir else None


def benzerlik_maliyeti(aranan, aday):
    if re.findall(r'\d+', aranan) != re.findall(r'\d+', aday):
        return None
    a, b = aranan.split(), aday.split()
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
    aranan = eslestirme_metni(yer_adi)
    if not aranan:
        return []

    gruplar = defaultdict(list)
    for satir in satirlar:
        gruplar[eslestirme_metni(satir[1])].append(satir)

    if aranan in gruplar:
        return gruplar[aranan]


    bosluksuz = aranan.replace(" ", "")
    ayni_yazim = [
        ad for ad in gruplar
        if ad.replace(" ", "") == bosluksuz
        and re.findall(r"\d+", ad) == re.findall(r"\d+", aranan)
    ]
    if len(ayni_yazim) == 1:
        return gruplar[ayni_yazim[0]]


    numaralar = re.findall(r'\d+', aranan)
    adaylar = {
        ad: kayitlar for ad, kayitlar in gruplar.items()
        if not numaralar or re.findall(r'\d+', ad) == numaralar
    }
    bastan = [
        s for ad, kayitlar in adaylar.items()
        if ad.startswith(aranan + ' ')
        for s in kayitlar
    ]
    if bastan:
        return bastan[:10]

    iceren = [
        s for ad, kayitlar in adaylar.items()
        if ' ' + aranan + ' ' in ' ' + ad + ' '
        for s in kayitlar
    ]
    if iceren:
        return iceren[:10]

    yakinlar = []
    for ad in gruplar:
        maliyet = benzerlik_maliyeti(aranan, ad)
        if maliyet is not None:
            yakinlar.append((maliyet, ad))
    yakinlar.sort()
    if not yakinlar:
        return []

   
    if len(yakinlar) > 1 and yakinlar[1][0] - yakinlar[0][0] < 2:
        return []
    return gruplar[yakinlar[0][1]]

def durak_ara(yer_adi):
    if not eslestirme_metni(yer_adi):
        return []
    with baglanti_ac() as baglanti:
        satirlar = baglanti.execute(
            '''
            SELECT durak_kodu, durak_adi, enlem, boylam
            FROM duraklar
            ORDER BY durak_adi, durak_kodu
            '''
        ).fetchall()
    return kayitlarda_ara(yer_adi, satirlar)
