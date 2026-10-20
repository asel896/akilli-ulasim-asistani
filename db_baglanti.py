import psycopg
from db import baglanti_ac

try:
    with baglanti_ac() as baglanti:
        with baglanti.cursor() as imlec:
            imlec.execute("SELECT current_database();")
            print("Veritabanı:", imlec.fetchone()[0])

            imlec.execute("SHOW client_encoding;")
            print("Bağlantı kodlaması:", imlec.fetchone()[0])

except psycopg.Error as hata:
    print("Bağlantı kurulamadı:", hata)