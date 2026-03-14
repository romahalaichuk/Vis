import sqlite3
import json
from typing import List, Dict
import uuid

DB_PATH = 'restauracja.db'

# skala
SCALE = 50  # 1m = 50px

# wielobok planszy w metrach
PLANSZA_PUNKTY_M = [
    (0, 0),
    (0, 9.5),
    (-4, 9.5),
    (-4, 6.5),
    (-11, 6.5),
    (-11, 0)
]

# konwersja do pikseli
PLANSZA_PUNKTY = [(x * SCALE, y * SCALE) for x, y in PLANSZA_PUNKTY_M]

# obliczenie wymiarów planszy
min_x = min(p[0] for p in PLANSZA_PUNKTY)
max_x = max(p[0] for p in PLANSZA_PUNKTY)
min_y = min(p[1] for p in PLANSZA_PUNKTY)
max_y = max(p[1] for p in PLANSZA_PUNKTY)

PLANSZA_SZER = max_x - min_x
PLANSZA_WYS = max_y - min_y
def init_sala_db():
    """Inicjalizacja tabel dla planszy"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Stoliki
    c.execute('''
        CREATE TABLE IF NOT EXISTS plansza_stoliki (
            id TEXT PRIMARY KEY,
            nazwa TEXT,
            szerokosc REAL,
            dlugosc REAL,
            poz_x REAL DEFAULT 0,
            poz_y REAL DEFAULT 0,
            kat REAL DEFAULT 0,
            kolor TEXT DEFAULT '#4ecdc4'
        )
    ''')
    
    # Krzesła
    c.execute('''
        CREATE TABLE IF NOT EXISTS plansza_krzesla (
            id TEXT PRIMARY KEY,
            nazwa TEXT,
            poz_x REAL DEFAULT 0,
            poz_y REAL DEFAULT 0,
            kat REAL DEFAULT 0,
            kolor TEXT DEFAULT '#ffa500'
        )
    ''')
    
    # Przeszkody (betonowe i drewniane)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plansza_przeszkody (
            id TEXT PRIMARY KEY,
            typ TEXT,  -- 'beton' lub 'drewno'
            nazwa TEXT,
            szerokosc REAL,
            dlugosc REAL,
            poz_x REAL DEFAULT 0,
            poz_y REAL DEFAULT 0,
            kat REAL DEFAULT 0
        )
    ''')
    
    # Zamówienia
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

def punkt_w_wieloboku(x: float, y: float) -> bool:
    """Sprawdza czy punkt jest wewnątrz wieloboku planszy (algorytm ray casting)"""
    # Przeskaluj do metrów
    xm = x / SCALE
    ym = y / SCALE
    
    punkty = PLANSZA_PUNKTY
    n = len(punkty)
    inside = False
    
    j = n - 1
    for i in range(n):
        xi, yi = punkty[i]
        xj, yj = punkty[j]
        
        if ((yi > ym) != (yj > ym)) and (xm < (xj - xi) * (ym - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside

def koliduje_z_przeszkoda(x: float, y: float, szer: float, dl: float, kat: float = 0, 
                          exclude_id: str = None) -> bool:
    """Sprawdza czy prostokąt koliduje z jakąkolwiek przeszkodą"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, poz_x, poz_y, szerokosc, dlugosc, kat FROM plansza_przeszkody")
    przeszkody = c.fetchall()
    conn.close()
    
    # Proste sprawdzenie AABB (axis-aligned bounding box)
    # Dla prostoty zakładamy małe obroty lub używamy przybliżenia
    for p in przeszkody:
        if exclude_id and p[0] == exclude_id:
            continue
            
        px, py, pszer, pdl = p[1], p[2], p[3] * SCALE, p[4] * SCALE
        
        # Sprawdź nakładanie się prostokątów
        if (x < px + pszer and x + szer > px and 
            y < py + pdl and y + dl > py):
            return True
    
    return False

def koliduje_z_przeszkoda_okrag(x: float, y: float, promien: float = 20) -> bool:
    """Sprawdza czy okrąg (krzesło) koliduje z przeszkodą"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT poz_x, poz_y, szerokosc, dlugosc FROM plansza_przeszkody")
    przeszkody = c.fetchall()
    conn.close()
    
    for px, py, pszer, pdl in przeszkody:
        pszer_px = pszer * SCALE
        pdl_px = pdl * SCALE
        
        # Najbliższy punkt w prostokącie do środka okręgu
        closest_x = max(px, min(x, px + pszer_px))
        closest_y = max(py, min(y, py + pdl_px))
        
        # Odległość od środka okręgu do najbliższego punktu
        dx = x - closest_x
        dy = y - closest_y
        distance = (dx**2 + dy**2) ** 0.5
        
        if distance < promien:
            return True
    
    return False

# ========== STOLIKI ==========

def dodaj_stolik(nazwa: str, szer: float, dl: float, 
                 poz_x: float = 0, poz_y: float = 0, 
                 kat: float = 0, kolor: str = '#4ecdc4') -> dict:
    
    # Sprawdź czy wewnątrz planszy
    if not punkt_w_wieloboku(poz_x + (szer*SCALE)/2, poz_y + (dl*SCALE)/2):
        raise ValueError("Stolik poza obszarem planszy")
    
    # Sprawdź kolizję z przeszkodami
    if koliduje_z_przeszkoda(poz_x, poz_y, szer*SCALE, dl*SCALE, kat):
        raise ValueError("Stolik koliduje z przeszkodą")
    
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
            'poz_x': poz_x, 'poz_y': poz_y, 'kat': kat, 'kolor': kolor, 'typ': 'stolik'}

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
    # Pobierz wymiary
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT szerokosc, dlugosc FROM plansza_stoliki WHERE id=?", (sid,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    
    szer, dl = row[0] * SCALE, row[1] * SCALE
    
    # Sprawdź czy wewnątrz planszy
    if not punkt_w_wieloboku(x + szer/2, y + dl/2):
        conn.close()
        raise ValueError("Poza planszą")
    
    # Sprawdź kolizję
    if koliduje_z_przeszkoda(x, y, szer, dl, kat or 0, sid):
        conn.close()
        raise ValueError("Kolizja z przeszkodą")
    
    if kat is not None:
        c.execute('UPDATE plansza_stoliki SET poz_x=?, poz_y=?, kat=? WHERE id=?',
                  (x, y, kat, sid))
    else:
        c.execute('UPDATE plansza_stoliki SET poz_x=?, poz_y=? WHERE id=?',
                  (x, y, sid))
    
    conn.commit()
    conn.close()

def usun_stolik(sid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM plansza_stoliki WHERE id=?", (sid,))
    conn.commit()
    conn.close()

# ========== KRZESŁA ==========

def dodaj_krzeslo(nazwa: str = "Krzesło", 
                  poz_x: float = 0, poz_y: float = 0,
                  kat: float = 0, kolor: str = '#ffa500') -> dict:
    
    # Sprawdź czy wewnątrz planszy (z marginesem)
    if not punkt_w_wieloboku(poz_x, poz_y):
        raise ValueError("Krzesło poza obszarem planszy")
    
    # Sprawdź kolizję z przeszkodami
    if koliduje_z_przeszkoda_okrag(poz_x, poz_y, 22):
        raise ValueError("Krzesło koliduje z przeszkodą")
    
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
    # Sprawdź czy wewnątrz planszy
    if not punkt_w_wieloboku(x, y):
        raise ValueError("Poza planszą")
    
    # Sprawdź kolizję
    if koliduje_z_przeszkoda_okrag(x, y, 22):
        raise ValueError("Kolizja z przeszkodą")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if kat is not None:
        c.execute('UPDATE plansza_krzesla SET poz_x=?, poz_y=?, kat=? WHERE id=?',
                  (x, y, kat, kid))
    else:
        c.execute('UPDATE plansza_krzesla SET poz_x=?, poz_y=? WHERE id=?',
                  (x, y, kid))
    
    conn.commit()
    conn.close()

def usun_krzeslo(kid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM plansza_krzesla WHERE id=?", (kid,))
    conn.commit()
    conn.close()

# ========== PRZESZKODY ==========

def dodaj_przeszkode(typ: str, nazwa: str, szer: float, dl: float,
                     poz_x: float = 0, poz_y: float = 0, kat: float = 0) -> dict:
    """typ: 'beton' lub 'drewno'"""
    
    # Sprawdź czy wewnątrz planszy
    if not punkt_w_wieloboku(poz_x + (szer*SCALE)/2, poz_y + (dl*SCALE)/2):
        raise ValueError("Przeszkoda poza obszarem planszy")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    pid = generuj_id("przesz")
    c.execute('''
        INSERT INTO plansza_przeszkody (id, typ, nazwa, szerokosc, dlugosc, poz_x, poz_y, kat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pid, typ, nazwa, szer, dl, poz_x, poz_y, kat))
    
    conn.commit()
    conn.close()
    
    kolor = '#808080' if typ == 'beton' else '#8B4513'
    return {
        'id': pid, 'typ': typ, 'nazwa': nazwa, 
        'szerokosc': szer, 'dlugosc': dl,
        'poz_x': poz_x, 'poz_y': poz_y, 'kat': kat,
        'kolor': kolor, 'typ': 'przeszkoda'
    }

def pobierz_przeszkody() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM plansza_przeszkody')
    rows = c.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        typ = r[1]
        kolor = '#808080' if typ == 'beton' else '#8B4513'
        result.append({
            'id': r[0], 'typ': typ, 'nazwa': r[2],
            'szerokosc': r[3], 'dlugosc': r[4],
            'poz_x': r[5], 'poz_y': r[6], 'kat': r[7],
            'kolor': kolor, 'typ': 'przeszkoda'
        })
    return result

def przesun_przeszkode(pid: str, x: float, y: float, kat: float = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if kat is not None:
        c.execute('UPDATE plansza_przeszkody SET poz_x=?, poz_y=?, kat=? WHERE id=?',
                  (x, y, kat, pid))
    else:
        c.execute('UPDATE plansza_przeszkody SET poz_x=?, poz_y=? WHERE id=?',
                  (x, y, pid))
    
    conn.commit()
    conn.close()

def usun_przeszkode(pid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM plansza_przeszkody WHERE id=?", (pid,))
    conn.commit()
    conn.close()

# ========== ZAMÓWIENIA ==========

def dodaj_zamowienie_krzeslo(kid: str, danie: str, kelner: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO krzeslo_zamowienia (krzeslo_id, danie_nazwa, ilosc, kelner)
        VALUES (?, ?, 1, ?)
    ''', (kid, danie, kelner))
    conn.commit()
    conn.close()

def pobierz_sale() -> dict:
    return {
        'stoliki': pobierz_stoliki(),
        'krzesla': pobierz_krzesla(),
        'przeszkody': pobierz_przeszkody(),
        'wymiary': {
            'szer': PLANSZA_SZER,
            'wys': PLANSZA_WYS
        },
        'punkty': PLANSZA_PUNKTY
    }

def pobierz_zamowienia_krzesla(kid: str) -> List[Dict]:
    """Pobiera wszystkie zamówienia dla konkretnego krzesła"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT id, danie_nazwa, ilosc, kelner, timestamp
        FROM krzeslo_zamowienia
        WHERE krzeslo_id = ?
        ORDER BY timestamp DESC
    """, (kid,))

    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "danie": r[1],
            "ilosc": r[2],
            "kelner": r[3],
            "timestamp": r[4]
        }
        for r in rows
    ]