import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

klasor = Path(__file__).resolve().parent
load_dotenv(klasor / ".env")


# ihtiyac duydugumuzda ayni ayarlarla yeni baglanti acar
def baglanti_ac():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        client_encoding="UTF8",
        connect_timeout=10
    )