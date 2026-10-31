CREATE TABLE IF NOT EXISTS sefer_saatleri (
    sefer_id BIGSERIAL PRIMARY KEY,
    hat_kodu VARCHAR(30) NOT NULL
        REFERENCES hatlar(hat_kodu),
    gun TEXT NOT NULL,
    yon VARCHAR(10) NOT NULL
        CHECK (yon IN ('gidis', 'donus')),
    saat TIME NOT NULL,
    aciklama TEXT NOT NULL DEFAULT '',
    UNIQUE (hat_kodu, gun, yon, saat, aciklama)
);