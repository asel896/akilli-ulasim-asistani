import json
import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from db import baglanti_ac


proje_klasoru = Path(__file__).resolve().parent
load_dotenv(proje_klasoru / ".env")

api_anahtari = os.getenv("GEMINI_API_KEY")

if not api_anahtari:
    raise ValueError(".env dosyasında GEMINI_API_KEY bulunamadı.")

istemci = genai.Client(api_key=api_anahtari)


def adresleri_coz(kullanici_cumlesi):
    istem = f"""
Kullanıcının toplu taşıma isteğinden başlangıç ve hedef yer adlarını çıkar.
Yalnızca JSON döndür. Açıklama veya Markdown ekleme.
Başlangıç belirtilmemişse baslangic değerini null yap.
Hedef belirtilmemişse hedef değerini null yap.

JSON biçimi:
{{"baslangic": "yer adı veya null", "hedef": "yer adı veya null"}}

Kullanıcı cümlesi: {kullanici_cumlesi}
"""

    yanit = istemci.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=istem
    )

    metin = yanit.text.strip()
    metin = re.sub(r"^```(?:json)?\s*|\s*```$", "", metin)

    return json.loads(metin)


def metni_normalize_et(metin):
    metin = metin.casefold().replace("ı", "i")
    metin = unicodedata.normalize("NFKD", metin)

    return "".join(
        karakter
        for karakter in metin
        if not unicodedata.combining(karakter)
    )


def durak_ara(yer_adi):
    if not yer_adi:
        return []

    with baglanti_ac() as baglanti:
        duraklar = baglanti.execute(
            """
            SELECT durak_kodu, durak_adi, enlem, boylam
            FROM duraklar
            ORDER BY durak_adi
            """
        ).fetchall()

    aranan = metni_normalize_et(yer_adi)

    return [
        durak
        for durak in duraklar
        if aranan in metni_normalize_et(durak[1])
    ][:10]


def dogrudan_hatlari_bul(baslangic_duraklari, hedef_duraklari):
    baslangic_kodlari = list({durak[0] for durak in baslangic_duraklari})
    hedef_kodlari = list({durak[0] for durak in hedef_duraklari})

    if not baslangic_kodlari or not hedef_kodlari:
        return []

    with baglanti_ac() as baglanti:
        hatlar = baglanti.execute(
            """
            SELECT DISTINCT
                h.hat_kodu,
                h.hat_adi,
                bas.yon,
                bas.sira,
                hedef.sira,
                bas.durak_kodu,
                hedef.durak_kodu,
                bas_durak.durak_adi,
                hedef_durak.durak_adi,
                hedef.sira - bas.sira AS durak_araligi
            FROM hat_duraklar AS bas
            JOIN hat_duraklar AS hedef
              ON hedef.hat_kodu = bas.hat_kodu
             AND hedef.yon = bas.yon
             AND bas.sira < hedef.sira
            JOIN hatlar AS h
              ON h.hat_kodu = bas.hat_kodu
            JOIN duraklar AS bas_durak
              ON bas_durak.durak_kodu = bas.durak_kodu
            JOIN duraklar AS hedef_durak
              ON hedef_durak.durak_kodu = hedef.durak_kodu
            WHERE h.hizmet_turu IS DISTINCT FROM 'gorevli'
              AND bas.durak_kodu = ANY(%s::varchar[])
              AND hedef.durak_kodu = ANY(%s::varchar[])
            ORDER BY durak_araligi, h.hat_kodu, bas.yon
            """,
            (baslangic_kodlari, hedef_kodlari)
        ).fetchall()

    return hatlar


def hat_duraklarini_getir(hat_kodu, yon, ilk_sira, son_sira):
    with baglanti_ac() as baglanti:
        duraklar = baglanti.execute(
            """
            SELECT hd.sira, hd.durak_kodu, d.durak_adi
            FROM hat_duraklar AS hd
            JOIN duraklar AS d
              ON d.durak_kodu = hd.durak_kodu
            WHERE hd.hat_kodu = %s
              AND hd.yon = %s
              AND hd.sira BETWEEN %s AND %s
            ORDER BY hd.sira
            """,
            (hat_kodu, yon, ilk_sira, son_sira)
        ).fetchall()

    return duraklar


def sefer_saatlerini_getir(hat_kodu, yon, gun):
    with baglanti_ac() as baglanti:
        saatler = baglanti.execute(
            """
            SELECT saat, aciklama
            FROM sefer_saatleri
            WHERE hat_kodu = %s
              AND yon = %s
              AND gun = %s
            ORDER BY saat
            """,
            (hat_kodu, yon, gun)
        ).fetchall()

    return saatler


cumle = input("Nereden nereye gitmek istiyorsun? ")

try:
    adresler = adresleri_coz(cumle)

    baslangic_yeri = adresler.get("baslangic")
    hedef_yeri = adresler.get("hedef")

    print(f"\nAnlaşılan başlangıç: {baslangic_yeri or 'Belirtilmedi'}")
    print(f"Anlaşılan hedef: {hedef_yeri or 'Belirtilmedi'}")

    baslangic_duraklari = durak_ara(baslangic_yeri)
    hedef_duraklari = durak_ara(hedef_yeri)

    if not baslangic_duraklari:
        print("\nBaşlangıç için eşleşen durak bulunamadı.")
    elif not hedef_duraklari:
        print("\nHedef için eşleşen durak bulunamadı.")
    else:
        bulunan_hatlar = dogrudan_hatlari_bul(
            baslangic_duraklari,
            hedef_duraklari
        )

        if not bulunan_hatlar:
            print("\nBu iki durak arasında doğrudan hat bulunamadı.")
            print("Aktarmalı yol bulma özelliğini sonraki aşamada ekleyeceğiz.")
        else:
            print("\nDoğrudan hat seçenekleri:")

            for sira, hat in enumerate(bulunan_hatlar, start=1):
                (
                    hat_kodu,
                    hat_adi,
                    yon,
                    ilk_sira,
                    son_sira,
                    baslangic_kodu,
                    hedef_kodu,
                    baslangic_durak_adi,
                    hedef_durak_adi,
                    durak_araligi
                ) = hat

                durak_sayisi = son_sira - ilk_sira + 1

                print(
                    f"{sira}. Hat {hat_kodu} | {hat_adi} | "
                    f"{yon} | {durak_sayisi} durak"
                )
                print(
                    f"   Biniş: {baslangic_durak_adi} "
                    f"→ İniş: {hedef_durak_adi}"
                )

            secim = int(
                input("\nDurak sırasını görmek istediğin seçeneğin numarası: ")
            )

            if secim < 1 or secim > len(bulunan_hatlar):
                print("Geçersiz seçenek numarası.")
            else:
                secilen_hat = bulunan_hatlar[secim - 1]

                (
                    hat_kodu,
                    hat_adi,
                    yon,
                    ilk_sira,
                    son_sira,
                    baslangic_kodu,
                    hedef_kodu,
                    baslangic_durak_adi,
                    hedef_durak_adi,
                    durak_araligi
                ) = secilen_hat

                print(f"\nHat {hat_kodu} durak sırası:")
                print(f"{baslangic_durak_adi} → {hedef_durak_adi}")

                guzergah_duraklari = hat_duraklarini_getir(
                    hat_kodu,
                    yon,
                    ilk_sira,
                    son_sira
                )

                for sira, kod, ad in guzergah_duraklari:
                    print(f"  {sira}. {ad} (Kod: {kod})")

                gunler = [
                    "Pazartesi",
                    "Salı",
                    "Çarşamba",
                    "Perşembe",
                    "Cuma",
                    "Cumartesi",
                    "Pazar",
                ]

                gun_eslesmeleri = {
                    metni_normalize_et(gun): gun
                    for gun in gunler
                }

                girilen_gun = input(
                    "\nSefer saatlerini görmek istediğin gün: "
                ).strip()

                gun = gun_eslesmeleri.get(
                    metni_normalize_et(girilen_gun)
                )

                if not gun:
                    print("Gün adını listedeki biçimlerden biriyle yazmalısın.")
                else:
                    saatler = sefer_saatlerini_getir(
                        hat_kodu,
                        yon,
                        gun
                    )

                    if saatler:
                        print(f"\nHat {hat_kodu} için {gun} sefer saatleri:")

                        for saat, aciklama in saatler:
                            saat_metni = saat.strftime("%H:%M") if hasattr(saat, "strftime") else str(saat)
                            ek_bilgi = f" ({aciklama})" if aciklama else ""
                            print(f"  {saat_metni}{ek_bilgi}")

                        if ilk_sira != 1:
                            print(
                                "\nNot: Bu saatler hattın başlangıç noktası "
                                "içindir; biniş durağından geçiş saatini göstermez."
                            )
                    else:
                        print(
                            f"\nHat {hat_kodu} için {gun} günü "
                            "veritabanında sefer saati bulunmuyor."
                        )

except json.JSONDecodeError:
    print("Gemini yanıtı beklenen JSON biçiminde gelmedi.")
except ValueError:
    print("Seçim alanına listedeki seçenek numarasını yazmalısın.")
except Exception as hata:
    print("İşlem sırasında hata oluştu:", hata)