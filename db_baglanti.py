import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

try:
    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=10
    ) as baglanti:

        with baglanti.cursor() as imlec:
            imlec.execute("SELECT current_database();")
            sonuc = imlec.fetchone()

            print("Bağlantı başarılı.")
            print("Bağlanılan veritabanı:", sonuc[0])

except psycopg.Error as hata:
    print("Veritabanı bağlantısı kurulamadı:", hata)