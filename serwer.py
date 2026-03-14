from flask import Flask, render_template_string, jsonify, request, session, redirect
from flask_socketio import SocketIO, emit
import sqlite3
import socket
import threading
import webbrowser
import qrcode
import io
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny-klucz-restauracji-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_PATH = 'restauracja.db'

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Usuń stare tabele jeśli mają złą strukturę
    c.execute("DROP TABLE IF EXISTS stoliki")
    c.execute("DROP TABLE IF EXISTS menu")
    c.execute("DROP TABLE IF EXISTS kelnerzy")
    
    # Stoliki - struktura zaczyna się od podstawowych pól, reszta dynamicznie
    c.execute('''CREATE TABLE IF NOT EXISTS stoliki 
                 (id INTEGER PRIMARY KEY, numer INTEGER UNIQUE)''')
    
    # Menu (dynamiczne)
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id INTEGER PRIMARY KEY, nazwa TEXT, ilosc INTEGER DEFAULT 0, kolor TEXT)''')
    
    # Kelnerzy
    c.execute('''CREATE TABLE IF NOT EXISTS kelnerzy 
                 (id INTEGER PRIMARY KEY, imie TEXT, aktywny INTEGER DEFAULT 1)''')
    
    # Inicjalizacja stolików
    for i in range(1, 11):
        c.execute("INSERT OR IGNORE INTO stoliki (numer) VALUES (?)", (i,))
    
    # Przykładowe dania
    c.execute("SELECT COUNT(*) FROM menu")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Łosoś', 20, '#ff6b6b')")
        c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Makaron', 20, '#4ecdc4')")
    
    conn.commit()
    conn.close()

def get_menu():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    dania = c.execute("SELECT id, nazwa, ilosc, kolor FROM menu").fetchall()
    conn.close()
    return [{'id': d[0], 'nazwa': d[1], 'ilosc': d[2], 'kolor': d[3]} for d in dania]

def get_stan():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Pobierz wszystkie kolumny tabeli stoliki
    c.execute("PRAGMA table_info(stoliki)")
    kolumny = [row[1] for row in c.fetchall()]
    
    # Pobierz dane stolików
    c.execute("SELECT * FROM stoliki")
    wiersze = c.fetchall()
    
    stoliki = []
    for wiersz in wiersze:
        stolik_dict = {}
        for i, kolumna in enumerate(kolumny):
            stolik_dict[kolumna] = wiersz[i]
        stoliki.append(stolik_dict)
    
    menu = c.execute("SELECT id, nazwa, ilosc, kolor FROM menu").fetchall()
    kelnerzy = c.execute("SELECT imie FROM kelnerzy WHERE aktywny=1").fetchall()
    
    conn.close()
    
    return {
        'stoliki': stoliki,
        'menu': [{'id': m[0], 'nazwa': m[1], 'ilosc': m[2], 'kolor': m[3]} for m in menu],
        'kelnerzy': [k[0] for k in kelnerzy]
    }

def generuj_qr(url):
    """Generuj QR kod jako base64 obrazek"""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

@app.route('/')
def index():
    stan = get_stan()
    ip = get_ip()
    port = 5000
    url = f"http://{ip}:{port}/kelner"
    qr_kod = generuj_qr(url)
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Zamówień - ADMIN</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 20px;
        }
        h1 { color: #e94560; font-size: 2rem; }
        .qr-section {
            background: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .qr-section:hover { transform: scale(1.05); }
        .qr-section img { width: 100px; height: 100px; }
        .qr-section p { color: #333; font-size: 0.8rem; margin-top: 5px; font-weight: bold; }
        
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 20px;
            text-align: center;
            max-width: 400px;
        }
        .modal-content img { width: 300px; height: 300px; margin-bottom: 20px; }
        .modal-content h2 { color: #333; margin-bottom: 10px; }
        .modal-content p { color: #666; margin-bottom: 20px; }
        .modal-content button {
            background: #e94560;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 1.1rem;
            cursor: pointer;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        
        .panel {
            background: #16213e;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .panel h2 {
            color: #e94560;
            margin-bottom: 15px;
            border-bottom: 2px solid #e94560;
            padding-bottom: 10px;
        }
        
        .danie-admin {
            background: #0f3460;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .danie-info { display: flex; align-items: center; gap: 15px; }
        .kolor {
            width: 30px; height: 30px;
            border-radius: 50%;
            border: 3px solid white;
        }
        .danie-nazwa { font-size: 1.2rem; font-weight: bold; }
        .danie-ilosc { font-size: 1.5rem; color: #4ecdc4; }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            margin-left: 5px;
        }
        .btn-dodaj { background: #4ecdc4; color: white; }
        .btn-odejmij { background: #ff6b6b; color: white; }
        .btn-usun { background: #666; color: white; }
        .btn-edytuj { background: #ffa500; color: white; }
        
        .nowe-danie {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .nowe-danie input {
            flex: 1;
            padding: 10px;
            border-radius: 5px;
            border: none;
            background: #0f3460;
            color: white;
        }
        
       .kelner-lista {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }
        .kelner-bubble {
            width: fit-content;
            background: #4ecdc4;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: bold;
        }
        
        .stolik-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }
        .stolik {
            background: #0f3460;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #e94560;
        }
        .stolik-nr { font-size: 1.3rem; color: #e94560; margin-bottom: 10px; font-weight: bold; }
        .zamowienie {
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 5px;
            font-size: 0.9rem;
        }
        .zamowienie strong { color: #4ecdc4; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🍽️ System Zamówień - PANEL KUCHARZA</h1>
        <div class="qr-section" onclick="pokazQR()">
            <img src="{{ qr_kod }}" alt="QR Kod">
            <p>KLIKNIJ PO QR DLA KELNERÓW</p>
        </div>
    </div>
    
    <div id="qrModal" class="modal" onclick="zamknijQR()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <h2>📱 Zeskanuj kod telefonem</h2>
            <img src="{{ qr_kod }}" alt="QR Kod">
            <p>Połącz telefon z WiFi: <strong>{{ ip }}</strong><br>
            Wejdź na: <strong>http://{{ ip }}:5000/kelner</strong></p>
            <button onclick="zamknijQR()">Zamknij</button>
        </div>
    </div>
    
    <div id="menuModal" class="modal" onclick="zamknijMenuModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <h2>🍳 Zarządzanie Daniami</h2>
            <div id="menu-lista"></div>
            <div class="nowe-danie">
                <input type="text" id="noweNazwa" placeholder="Nazwa dania">
                <input type="number" id="noweIlosc" placeholder="Ilość">
                <input type="color" id="noweKolor" value="#ff6b6b">
                <button class="btn btn-dodaj" onclick="dodajDanie()">+ Dodaj</button>
            </div>
            <button onclick="zamknijMenuModal()" style="margin-top: 15px;">Zamknij</button>
        </div>
    </div>
    
    <div class="grid">
        <div>
            <div class="panel">
                <button class="btn btn-dodaj" onclick="otworzMenuModal()">
                    🍳 Zarządzanie Daniami
                </button>
            </div>
            <div class="panel">
                <h2>👥 Aktywni Kelnerzy</h2>
                <div id="kelnerzy-lista" class="kelner-lista">
                    <p style="color: #888;">Brak zalogowanych kelnerów</p>
                </div>
            </div>
        </div>
        <div>
            <div class="panel">
                <h2>🪑 Stoliki (w czasie rzeczywistym)</h2>
                <div id="stoliki-lista" class="stolik-grid"></div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        
        function otworzMenuModal(){
            document.getElementById("menuModal").style.display="flex";
        }
        function zamknijMenuModal(){
            document.getElementById("menuModal").style.display="none";
        }
        function pokazQR() {
            document.getElementById('qrModal').style.display = 'flex';
        }
        function zamknijQR() {
            document.getElementById('qrModal').style.display = 'none';
        }
        
        function render(data) {
            const menuDiv = document.getElementById('menu-lista');
            menuDiv.innerHTML = '';
            data.menu.forEach(danie => {
                menuDiv.innerHTML += `
                    <div class="danie-admin">
                        <div class="danie-info">
                            <div class="kolor" style="background: ${danie.kolor}"></div>
                            <div>
                                <div class="danie-nazwa">${danie.nazwa}</div>
                                <div class="danie-ilosc">${danie.ilosc} szt.</div>
                            </div>
                        </div>
                        <div>
                            <button class="btn btn-odejmij" onclick="zmienIlosc(${danie.id}, -1)">-1</button>
                            <button class="btn btn-dodaj" onclick="zmienIlosc(${danie.id}, 1)">+1</button>
                            <button class="btn btn-edytuj" onclick="edytujDanie(${danie.id})">✎</button>
                            <button class="btn btn-usun" onclick="usunDanie(${danie.id})">🗑</button>
                        </div>
                    </div>
                `;
            });
            
            const kelnerDiv = document.getElementById('kelnerzy-lista');
            if (data.kelnerzy.length > 0) {
                kelnerDiv.innerHTML = data.kelnerzy.map(k => 
                    `<div class="kelner-bubble">${k}</div>`
                ).join('');
            } else {
                kelnerDiv.innerHTML = '<p style="color: #888;">Brak zalogowanych kelnerów</p>';
            }
            
            const stolikiDiv = document.getElementById('stoliki-lista');
            stolikiDiv.innerHTML = '';
            data.stoliki.forEach(s => {
                let zamowienia = '';
                data.menu.forEach(danie => {
                    const nazwaLower = danie.nazwa.toLowerCase();
                    const ilosc = s[nazwaLower] || 0;
                    const kelner = s['kelner_' + nazwaLower] || '?';
                    if (ilosc > 0) {
                        zamowienia += `<div class="zamowienie">${danie.nazwa}: <strong>${ilosc}</strong> (${kelner})</div>`;
                    }
                });
                if (!zamowienia) zamowienia = '<div style="color: #888;">Pusty</div>';
                
                stolikiDiv.innerHTML += `
                    <div class="stolik">
                        <div class="stolik-nr">Stolik ${s.numer}</div>
                        ${zamowienia}
                    </div>
                `;
            });
        }
        
        function dodajDanie() {
            const nazwa = document.getElementById('noweNazwa').value;
            const ilosc = parseInt(document.getElementById('noweIlosc').value);
            const kolor = document.getElementById('noweKolor').value;
            
            if (nazwa && ilosc) {
                fetch('/api/menu', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({nazwa, ilosc, kolor})
                });
                document.getElementById('noweNazwa').value = '';
                document.getElementById('noweIlosc').value = '';
            }
        }
        
        function zmienIlosc(id, zmiana) {
            fetch(`/api/menu/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({zmiana})
            });
        }
        
        function usunDanie(id) {
            if (confirm('Usunąć to danie?')) {
                fetch(`/api/menu/${id}`, {method: 'DELETE'});
            }
        }
        
        function edytujDanie(id) {
            const nowaNazwa = prompt('Nowa nazwa:');
            if (nowaNazwa) {
                fetch(`/api/menu/${id}/nazwa`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({nazwa: nowaNazwa})
                });
            }
        }
        
        socket.on('aktualizacja', render);
        fetch('/api/stan').then(r => r.json()).then(render);
    </script>
</body>
</html>
    ''', qr_kod=qr_kod, ip=ip, port=port, stan=stan, menu=stan['menu'])

@app.route('/kelner')
def kelner():
    return render_template_string('''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kelner - System Zamówień</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 15px;
            max-width: 500px;
            margin: 0 auto;
        }
        .login-screen {
            text-align: center;
            padding-top: 50px;
        }
        .login-screen h1 { color: #e94560; margin-bottom: 30px; }
        .login-screen input {
            width: 100%;
            padding: 20px;
            font-size: 1.3rem;
            border-radius: 10px;
            border: 2px solid #e94560;
            background: #16213e;
            color: white;
            text-align: center;
            margin-bottom: 20px;
        }
        .login-screen button {
            width: 100%;
            padding: 20px;
            font-size: 1.2rem;
            background: #e94560;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e94560;
        }
        .header h1 { color: #e94560; font-size: 1.5rem; }
        .moje-imie {
            background: #4ecdc4;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: bold;
        }
        .wyloguj {
            background: #666;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            margin-left: 10px;
        }
        .menu-info {
            background: #16213e;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .danie-dostepne {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            background: #0f3460;
        }
        .danie-nazwa { font-size: 1.2rem; font-weight: bold; }
        .danie-ilosc { font-size: 1.5rem; }
        .brak { opacity: 0.3; }
        .stoliki-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 15px;
        }
        .stolik {
            background: #16213e;
            border-radius: 15px;
            padding: 20px;
            border-left: 5px solid #e94560;
        }
        .stolik-nr {
            font-size: 1.3rem;
            color: #e94560;
            margin-bottom: 15px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }
        .zamowienia-moje {
            background: rgba(78, 205, 196, 0.2);
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 15px;
            border: 1px solid #4ecdc4;
        }
        .zamowienia-moje h4 { color: #4ecdc4; margin-bottom: 5px; }
        .przyciski {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .btn-danie {
            padding: 20px;
            border: none;
            border-radius: 10px;
            font-size: 1.1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-danie:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        .btn-danie:active:not(:disabled) {
            transform: scale(0.95);
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div id="loginScreen" class="login-screen">
        <h1>🍽️ System Zamówień</h1>
        <p style="margin-bottom: 30px; color: #888;">Witaj! Podaj swoje imię:</p>
        <input type="text" id="imieInput" placeholder="Twoje imię" maxlength="20">
        <button onclick="zaloguj()">Wejdź do systemu</button>
    </div>
    
    <div id="appScreen" class="hidden">
        <div class="header">
            <h1>🍽️ Zamówienia</h1>
            <div>
                <span class="moje-imie" id="mojeImie">Kelner</span>
                <button class="wyloguj" onclick="wyloguj()">×</button>
            </div>
        </div>
        <div class="menu-info" id="menuInfo">
            <h3 style="margin-bottom: 15px; color: #e94560;">📦 Dostępność:</h3>
            <div id="daniaLista"></div>
        </div>
        <div id="stolikiLista" class="stoliki-grid"></div>
    </div>

    <script>
        let mojeImie = localStorage.getItem('kelnerImie');
        const socket = io();
        
        if (mojeImie) {
            pokazApp();
            socket.emit('zaloguj', {imie: mojeImie});
        }
        
        function zaloguj() {
            const imie = document.getElementById('imieInput').value.trim();
            if (imie.length < 2) {
                alert('Wpisz przynajmniej 2 znaki!');
                return;
            }
            mojeImie = imie;
            localStorage.setItem('kelnerImie', imie);
            socket.emit('zaloguj', {imie: imie});
            pokazApp();
        }
        
        function wyloguj() {
            localStorage.removeItem('kelnerImie');
            socket.emit('wyloguj', {imie: mojeImie});
            location.reload();
        }
        
        function pokazApp() {
            document.getElementById('loginScreen').classList.add('hidden');
            document.getElementById('appScreen').classList.remove('hidden');
            document.getElementById('mojeImie').textContent = mojeImie;
        }
        
        function render(data) {
            const daniaDiv = document.getElementById('daniaLista');
            daniaDiv.innerHTML = '';
            data.menu.forEach(danie => {
                const brak = danie.ilosc <= 0;
                daniaDiv.innerHTML += `
                    <div class="danie-dostepne ${brak ? 'brak' : ''}" style="border-left: 5px solid ${danie.kolor}">
                        <span class="danie-nazwa">${danie.nazwa}</span>
                        <span class="danie-ilosc" style="color: ${danie.kolor}">${danie.ilosc}</span>
                    </div>
                `;
            });
            
            const stolikiDiv = document.getElementById('stolikiLista');
            stolikiDiv.innerHTML = '';
            
            data.stoliki.forEach(stolik => {
                let mojeZamowienia = {};
                let mojeZamowieniaHTML = '';
                
                data.menu.forEach(danie => {
                    const nazwaLower = danie.nazwa.toLowerCase();
                    const kelnerKey = 'kelner_' + nazwaLower;
                    const iloscKey = nazwaLower;
                    
                    if (stolik[kelnerKey] === mojeImie && stolik[iloscKey] > 0) {
                        mojeZamowienia[danie.nazwa] = stolik[iloscKey];
                    }
                });
                
                if (Object.keys(mojeZamowienia).length > 0) {
                    mojeZamowieniaHTML = '<div class="zamowienia-moje"><h4>👤 Twoje zamówienia:</h4>';
                    for (let [nazwa, ilosc] of Object.entries(mojeZamowienia)) {
                        mojeZamowieniaHTML += `<div>${nazwa}: ${ilosc}</div>`;
                    }
                    mojeZamowieniaHTML += '</div>';
                }
                
                let przyciskiHTML = '<div class="przyciski">';
                data.menu.forEach(danie => {
                    const dostepne = danie.ilosc > 0;
                    const nazwaLower = danie.nazwa.toLowerCase();
                    przyciskiHTML += `
                        <button class="btn-danie" 
                                style="background: ${danie.kolor}; color: white;"
                                onclick="dodaj(${stolik.numer}, '${nazwaLower}', '${danie.nazwa}')"
                                ${!dostepne ? 'disabled' : ''}>
                            + ${danie.nazwa.toUpperCase()}
                        </button>
                    `;
                });
                przyciskiHTML += '</div>';
                
                const sumaZamowien = data.menu.reduce((sum, danie) => {
                    return sum + (stolik[danie.nazwa.toLowerCase()] || 0);
                }, 0);
                
                stolikiDiv.innerHTML += `
                    <div class="stolik">
                        <div class="stolik-nr">
                            Stolik ${stolik.numer}
                            ${sumaZamowien > 0 ? 
                                `<span style="font-size: 0.9rem; color: #888;">Suma: ${sumaZamowien}</span>` : ''}
                        </div>
                        ${mojeZamowieniaHTML}
                        ${przyciskiHTML}
                    </div>
                `;
            });
        }
        
        function dodaj(stolik, danieKey, danieNazwa) {
            socket.emit('dodaj_danie', {
                stolik: stolik, 
                danie: danieKey,
                danie_nazwa: danieNazwa,
                kelner: mojeImie
            });
        }
        
        socket.on('aktualizacja', render);
        fetch('/api/stan').then(r => r.json()).then(render);
    </script>
</body>
</html>
    ''')

@app.route('/api/stan')
def api_stan():
    return jsonify(get_stan())

@app.route('/api/menu', methods=['POST'])
def dodaj_menu():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES (?, ?, ?)",
              (data['nazwa'], data['ilosc'], data['kolor']))
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja', get_stan())
    return jsonify({'ok': True})

@app.route('/api/menu/<int:id>', methods=['PUT'])
def edytuj_menu(id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if 'zmiana' in data:
        c.execute("UPDATE menu SET ilosc = MAX(0, ilosc + ?) WHERE id=?", (data['zmiana'], id))
    
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja', get_stan())
    return jsonify({'ok': True})

@app.route('/api/menu/<int:id>/nazwa', methods=['PUT'])
def zmien_nazwe(id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE menu SET nazwa=? WHERE id=?", (data['nazwa'], id))
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja', get_stan())
    return jsonify({'ok': True})

@app.route('/api/menu/<int:id>', methods=['DELETE'])
def usun_menu(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM menu WHERE id=?", (id,))
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja', get_stan())
    return jsonify({'ok': True})

@socketio.on('zaloguj')
def handle_zaloguj(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM kelnerzy WHERE imie=?", (data['imie'],))
    if not c.fetchone():
        c.execute("INSERT INTO kelnerzy (imie) VALUES (?)", (data['imie'],))
    else:
        c.execute("UPDATE kelnerzy SET aktywny=1 WHERE imie=?", (data['imie'],))
    conn.commit()
    conn.close()
    emit('aktualizacja', get_stan(), broadcast=True)

@socketio.on('wyloguj')
def handle_wyloguj(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE kelnerzy SET aktywny=0 WHERE imie=?", (data['imie'],))
    conn.commit()
    conn.close()
    emit('aktualizacja', get_stan(), broadcast=True)

@socketio.on('dodaj_danie')
def handle_dodaj(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    stolik = data['stolik']
    danie = data['danie']
    danie_nazwa = data.get('danie_nazwa', danie.capitalize())
    kelner = data['kelner']
    
    c.execute("SELECT ilosc FROM menu WHERE nazwa=?", (danie_nazwa,))
    wynik = c.fetchone()
    
    if wynik and wynik[0] > 0:
        c.execute("PRAGMA table_info(stoliki)")
        kolumny = [row[1] for row in c.fetchall()]
        
        if danie not in kolumny:
            c.execute(f"ALTER TABLE stoliki ADD COLUMN {danie} INTEGER DEFAULT 0")
            c.execute(f"ALTER TABLE stoliki ADD COLUMN kelner_{danie} TEXT")
            conn.commit()
        
        c.execute(f"UPDATE stoliki SET {danie} = COALESCE({danie}, 0) + 1, kelner_{danie}=? WHERE numer=?", 
                  (kelner, stolik))
        c.execute("UPDATE menu SET ilosc = ilosc - 1 WHERE nazwa=?", (danie_nazwa,))
        conn.commit()
    
    conn.close()
    emit('aktualizacja', get_stan(), broadcast=True)

if __name__ == '__main__':
    init_db()
    
    IP = get_ip()
    PORT = 5000
    
    print(f"\n{'='*60}")
    print(f"🍽️  SYSTEM ZAMÓWIEŃ URUCHOMIONY!")
    print(f"{'='*60}")
    print(f"\n📱 Panel kelnera: http://{IP}:{PORT}/kelner")
    print(f"🖥️  Panel kucharza (TY): http://{IP}:{PORT}")
    print(f"    lub: http://127.0.0.1:{PORT}")
    print(f"\n💡 Kliknij QR kod w prawym górnym rogu aby pokazać kelnerom!")
    print(f"{'='*60}\n")
    
    threading.Timer(2.0, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)