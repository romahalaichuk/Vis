import sqlite3
import json
from typing import List, Dict
import uuid

DB_PATH = 'restauracja.db'

def init_sala_db():
    """Inicjalizacja tabel dla planszy"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Stoliki (tylko wizualne, bez zamówień)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plansza_stoliki (
            id TEXT PRIMARY KEY,
            nazwa TEXT,
            szerokosc REAL,
            dlugosc REAL,
            poz_x REAL DEFAULT 50,
            poz_y REAL DEFAULT 50,
            kat REAL DEFAULT 0,
            kolor TEXT DEFAULT '#4ecdc4'
        )
    ''')
    
    # Krzesła (niezależne, z zamówieniami)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plansza_krzesla (
            id TEXT PRIMARY KEY,
            nazwa TEXT,
            poz_x REAL DEFAULT 100,
            poz_y REAL DEFAULT 100,
            kat REAL DEFAULT 0,
            kolor TEXT DEFAULT '#ffa500'
        )
    ''')
    
    # Zamówienia per krzesło
    c.execute('''
        CREATE TABLE IF NOT EXISTS krzeslo_zamowienia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            krzeslo_id TEXT,
            danie_nazwa TEXT,
            ilosc INTEGER DEFAULT 1,
            kelner TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (krzeslo_id) REFERENCES plansza_krzesla(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def generuj_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

# ========== STOLIKI (wizualne) ==========

def dodaj_stolik(nazwa: str, szer: float, dl: float, 
                 poz_x: float = 50, poz_y: float = 50, 
                 kat: float = 0, kolor: str = '#4ecdc4') -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    sid = generuj_id("stol")
    c.execute('''
        INSERT INTO plansza_stoliki (id, nazwa, szerokosc, dlugosc, poz_x, poz_y, kat, kolor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (sid, nazwa, szer, dl, poz_x, poz_y, kat, kolor))
    
    conn.commit()
    conn.close()
    return {'id': sid, 'nazwa': nazwa, 'szerokosc': szer, 'dlugosc': dl, 
            'poz_x': poz_x, 'poz_y': poz_y, 'kat': kat, 'kolor': kolor}

def pobierz_stoliki() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM plansza_stoliki')
    rows = c.fetchall()
    conn.close()
    
    return [{
        'id': r[0], 'nazwa': r[1], 'szerokosc': r[2], 'dlugosc': r[3],
        'poz_x': r[4], 'poz_y': r[5], 'kat': r[6], 'kolor': r[7], 'typ': 'stolik'
    } for r in rows]

def przesun_stolik(sid: str, x: float, y: float, kat: float = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if kat is not None:
        c.execute('UPDATE plansza_stoliki SET poz_x=?, poz_y=?, kat=? WHERE id=?', (x, y, kat, sid))
    else:
        c.execute('UPDATE plansza_stoliki SET poz_x=?, poz_y=? WHERE id=?', (x, y, sid))
    conn.commit()
    conn.close()

def usun_stolik(sid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM plansza_stoliki WHERE id=?', (sid,))
    conn.commit()
    conn.close()

# ========== KRZESŁA (z zamówieniami) ==========

def dodaj_krzeslo(nazwa: str = "Krzesło", 
                  poz_x: float = 100, poz_y: float = 100,
                  kat: float = 0, kolor: str = '#ffa500') -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    kid = generuj_id("krz")
    c.execute('''
        INSERT INTO plansza_krzesla (id, nazwa, poz_x, poz_y, kat, kolor)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (kid, nazwa, poz_x, poz_y, kat, kolor))
    
    conn.commit()
    conn.close()
    return {'id': kid, 'nazwa': nazwa, 'poz_x': poz_x, 'poz_y': poz_y, 
            'kat': kat, 'kolor': kolor, 'zamowienia': [], 'typ': 'krzeslo'}

def pobierz_krzesla() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT * FROM plansza_krzesla')
    rows = c.fetchall()
    
    krzesla = []
    for r in rows:
        kid = r[0]
        # Pobierz zamówienia
        c.execute('''
            SELECT danie_nazwa, SUM(ilosc) as ilosc, kelner, MAX(timestamp) as czas
            FROM krzeslo_zamowienia 
            WHERE krzeslo_id=? 
            GROUP BY danie_nazwa, kelner
        ''', (kid,))
        zam = [{'danie': z[0], 'ilosc': z[1], 'kelner': z[2], 'timestamp': z[3]} 
               for z in c.fetchall()]
        
        krzesla.append({
            'id': kid, 'nazwa': r[1], 'poz_x': r[2], 'poz_y': r[3],
            'kat': r[4], 'kolor': r[5], 'zamowienia': zam, 'typ': 'krzeslo'
        })
    
    conn.close()
    return krzesla

def przesun_krzeslo(kid: str, x: float, y: float, kat: float = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if kat is not None:
        c.execute('UPDATE plansza_krzesla SET poz_x=?, poz_y=?, kat=? WHERE id=?', (x, y, kat, kid))
    else:
        c.execute('UPDATE plansza_krzesla SET poz_x=?, poz_y=? WHERE id=?', (x, y, kid))
    conn.commit()
    conn.close()

def usun_krzeslo(kid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM plansza_krzesla WHERE id=?', (kid,))
    conn.commit()
    conn.close()

def dodaj_zamowienie_krzeslo(kid: str, danie: str, kelner: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO krzeslo_zamowienia (krzeslo_id, danie_nazwa, ilosc, kelner)
        VALUES (?, ?, 1, ?)
    ''', (kid, danie, kelner))
    conn.commit()
    conn.close()

def usun_zamowienie_krzeslo(zam_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM krzeslo_zamowienia WHERE id=?', (zam_id,))
    conn.commit()
    conn.close()

def pobierz_zamowienia_krzesla(kid: str) -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT id, danie_nazwa, ilosc, kelner, timestamp 
        FROM krzeslo_zamowienia 
        WHERE krzeslo_id=? 
        ORDER BY timestamp DESC
    ''', (kid,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'danie': r[1], 'ilosc': r[2], 'kelner': r[3], 'timestamp': r[4]} 
            for r in rows]

def pobierz_sale() -> dict:
    return {
        'stoliki': pobierz_stoliki(),
        'krzesla': pobierz_krzesla(),
        'wymiary': {'szer': 800, 'wys': 600}
    }