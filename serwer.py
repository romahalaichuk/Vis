from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
import sqlite3
import socket
import threading
import webbrowser
import qrcode
import io
import base64

from kloc import (
    init_sala_db, dodaj_stolik, dodaj_krzeslo, pobierz_sale,
    przesun_stolik, przesun_krzeslo, usun_stolik, usun_krzeslo,
    dodaj_zamowienie_krzeslo, pobierz_zamowienia_krzesla
)

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
    
    c.execute("DROP TABLE IF EXISTS menu")
    c.execute("DROP TABLE IF EXISTS kelnerzy")
    
    c.execute('''CREATE TABLE menu (id INTEGER PRIMARY KEY, nazwa TEXT, ilosc INTEGER DEFAULT 0, kolor TEXT)''')
    c.execute('''CREATE TABLE kelnerzy (id INTEGER PRIMARY KEY, imie TEXT, aktywny INTEGER DEFAULT 1)''')
    
    # Przykładowe dania
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Łosoś', 20, '#ff6b6b')")
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Makaron', 20, '#4ecdc4')")
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Pizza', 15, '#ffa500')")
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES ('Sałatka', 25, '#90ee90')")
    
    conn.commit()
    conn.close()
    init_sala_db()

def get_menu():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    dania = c.execute("SELECT id, nazwa, ilosc, kolor FROM menu").fetchall()
    conn.close()
    return [{'id': d[0], 'nazwa': d[1], 'ilosc': d[2], 'kolor': d[3]} for d in dania]

def get_kelnerzy():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    kelnerzy = c.execute("SELECT imie FROM kelnerzy WHERE aktywny=1").fetchall()
    conn.close()
    return [k[0] for k in kelnerzy]

def generuj_qr(url):
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
    stan = {'menu': get_menu(), 'kelnerzy': get_kelnerzy()}
    ip = get_ip()
    url = f"http://{ip}:5000/kelner"
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
            min-height: 100vh;
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
            grid-template-columns: 350px 1fr;
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
        
        .nowe-danie {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .nowe-danie input {
            flex: 1;
            min-width: 100px;
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
        
        /* PLANSZA */
        .plansza-container {
            background: #0f3460;
            border-radius: 15px;
            padding: 20px;
            position: relative;
            overflow: auto;
            min-height: 500px;
        }
        .plansza {
            width: 800px;
            height: 600px;
            background: 
                linear-gradient(rgba(78, 205, 196, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(78, 205, 196, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            background-color: #1a1a2e;
            border: 2px solid #e94560;
            position: relative;
            margin: 0 auto;
        }
        
        /* Stolik na planszy */
        .stolik-obiekt {
            position: absolute;
            border: 3px solid white;
            border-radius: 8px;
            cursor: move;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 12px;
            user-select: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .stolik-obiekt:hover {
            box-shadow: 0 0 20px rgba(78, 205, 196, 0.8);
        }
        .stolik-obiekt .obrot {
            position: absolute;
            width: 55px;
            height: 55px;
            background: #ffa500;
            border-radius: 50%;
            cursor: grab;
            display: none;
        }
        .stolik-obiekt:hover .obrot { display: block; }
        .stolik-obiekt .usun {
            position: absolute;
            top: -10px;
            left: -10px;
            width: 20px;
            height: 20px;
            background: #ff6b6b;
            border-radius: 50%;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 12px;
        }
        .stolik-obiekt:hover .usun { display: flex; }
        
        /* Krzesło na planszy */
        .krzeslo-obiekt {
            position: absolute;
            width: 35px;
            height: 35px;
            border: 2px solid white;
            border-radius: 50%;
            cursor: move;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: bold;
            user-select: none;
            transition: transform 0.2s;
        }
        .krzeslo-obiekt:hover { transform: scale(1.2); z-index: 100; }
        .krzeslo-obiekt.ma-zamowienie {
            animation: pulse 1.5s infinite;
            border-color: #ff6b6b;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 5px currentColor; }
            50% { box-shadow: 0 0 20px currentColor; }
        }
        .krzeslo-obiekt .usun {
            position: absolute;
            top: -8px;
            right: -8px;
            width: 16px;
            height: 16px;
            background: #ff6b6b;
            border-radius: 50%;
            cursor: pointer;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 10px;
        }
        .krzeslo-obiekt:hover .usun { display: flex; }
        
        /* Tooltip zamówień */
        .zamowienia-tooltip {
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.9);
            padding: 10px;
            border-radius: 8px;
            min-width: 150px;
            display: none;
            z-index: 1000;
            border: 1px solid #4ecdc4;
        }
        .krzeslo-obiekt:hover .zamowienia-tooltip { display: block; }
        .zamowienia-tooltip h5 { color: #4ecdc4; margin-bottom: 5px; font-size: 11px; }
        .zamowienia-tooltip div { font-size: 10px; margin-bottom: 3px; }
        
        /* Panel dodawania */
        .dodaj-panel {
            background: #0f3460;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        .dodaj-panel h4 { color: #4ecdc4; margin-bottom: 10px; }
        .dodaj-panel input {
            width: 100%;
            padding: 8px;
            margin-bottom: 8px;
            border-radius: 5px;
            border: none;
            background: #1a1a2e;
            color: white;
        }
        .dodaj-panel .row {
            display: flex;
            gap: 8px;
        }
        .dodaj-panel .row input { flex: 1; }
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

    <div class="grid">
        <!-- LEWA KOLUMNA -->
        <div>
            <!-- Zarządzanie daniami -->
            <div class="panel">
                <h2>🍳 Zarządzanie Daniami</h2>
                <div id="menu-lista"></div>
                <div class="nowe-danie">
                    <input type="text" id="noweNazwa" placeholder="Nazwa dania">
                    <input type="number" id="noweIlosc" placeholder="Ilość" style="width:80px;">
                    <input type="color" id="noweKolor" value="#ff6b6b" style="width:50px;">
                    <button class="btn btn-dodaj" onclick="dodajDanie()">+</button>
                </div>
            </div>
            
            <!-- Dodawanie stolików i krzeseł -->
            <div class="panel">
                <h2>🪑 Dodaj do planszy</h2>
                
                <div class="dodaj-panel">
                    <h4>Stolik</h4>
                    <input type="text" id="stolNazwa" placeholder="Nazwa (np. Stolik VIP)" value="Stolik 1">
                    <div class="row">
                        <input type="number" id="stolSzer" placeholder="Szer (m)" value="1.5" step="0.1">
                        <input type="number" id="stolDl" placeholder="Dł (m)" value="1" step="0.1">
                    </div>
                    <input type="color" id="stolKolor" value="#4ecdc4">
                    <button class="btn btn-dodaj" onclick="dodajStolik()" style="width:100%; margin-top:8px;">
                        Dodaj stolik
                    </button>
                </div>
                
                <div class="dodaj-panel">
                    <h4>Krzesło (zamówienia)</h4>
                    <input type="text" id="krzNazwa" placeholder="Nazwa (np. Krzesło A)" value="Krzesło">
                    <input type="color" id="krzKolor" value="#ffa500">
                    <button class="btn btn-dodaj" onclick="dodajKrzeslo()" style="width:100%; margin-top:8px;">
                        Dodaj krzesło
                    </button>
                </div>
            </div>
            
            <!-- Aktywni kelnerzy -->
            <div class="panel">
                <h2>👥 Aktywni Kelnerzy</h2>
                <div id="kelnerzy-lista" class="kelner-lista">
                    <p style="color: #888;">Brak zalogowanych kelnerów</p>
                </div>
            </div>
        </div>
        
        <!-- PRAWA KOLUMNA - PLANSZA -->
        <div>
            <div class="panel">
                <h2>🗺️ Plansza Sali (przeciągaj i obracaj)</h2>
                <div class="plansza-container">
                    <div class="plansza" id="plansza"></div>
                </div>
                <p style="color:#888; margin-top:10px; font-size:0.9rem;">
                    💡 Stoliki: przeciągaj, obracaj pomarańczowym kółkiem | Krzesła: przeciągaj, mają własne ID i zamówienia
                </p>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        const SCALE = 50; // 1 metr = 50px
        
        let przeciagany = null;
        let obracany = null;
        let offsetX = 0, offsetY = 0;
        let startKat = 0;
        
        // Inicjalizacja
        fetch('/api/stan').then(r => r.json()).then(render);
        
        function render(data) {
            // Menu
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
                        </div>
                    </div>
                `;
            });
            
            // Kelnerzy
            const kelnerDiv = document.getElementById('kelnerzy-lista');
            if (data.kelnerzy.length > 0) {
                kelnerDiv.innerHTML = data.kelnerzy.map(k => 
                    `<div class="kelner-bubble">${k}</div>`
                ).join('');
            } else {
                kelnerDiv.innerHTML = '<p style="color: #888;">Brak zalogowanych kelnerów</p>';
            }
            
            // Plansza
            renderPlansza(data.sala);
        }
        
        function renderPlansza(sala) {
            const plansza = document.getElementById('plansza');
            plansza.innerHTML = '';
            
            // Stoliki
            sala.stoliki.forEach(s => {
                const div = document.createElement('div');
                div.className = 'stolik-obiekt';
                div.id = s.id;
                div.style.width = (s.szerokosc * SCALE) + 'px';
                div.style.height = (s.dlugosc * SCALE) + 'px';
                div.style.left = s.poz_x + 'px';
                div.style.top = s.poz_y + 'px';
                div.style.transform = `rotate(${s.kat}deg)`;
                div.style.background = s.kolor;
                div.innerHTML = `
                    ${s.nazwa}
                    <div class="obrot" onmousedown="startObrot(event, '${s.id}')">↻</div>
                    <div class="usun" onclick="usunStolik('${s.id}', event)">×</div>
                `;
                div.onmousedown = (e) => startDrag(e, s.id, 'stolik');
                plansza.appendChild(div);
            });
            
            // Krzesła
            sala.krzesla.forEach(k => {
                const div = document.createElement('div');
                div.className = 'krzeslo-obiekt' + (k.zamowienia.length > 0 ? ' ma-zamowienie' : '');
                div.id = k.id;
                div.style.left = k.poz_x + 'px';
                div.style.top = k.poz_y + 'px';
                div.style.transform = `rotate(${k.kat}deg)`;
                div.style.background = k.kolor;
                
                // Tooltip zamówień
                let tooltipHTML = '<div class="zamowienia-tooltip"><h5>Zamówienia:</h5>';
                if (k.zamowienia.length === 0) {
                    tooltipHTML += '<div>Brak zamówień</div>';
                } else {
                    k.zamowienia.forEach(z => {
                        tooltipHTML += `<div>${z.danie} x${z.ilosc} (${z.kelner})</div>`;
                    });
                }
                tooltipHTML += '</div>';
                
                div.innerHTML = `
                    ${k.nazwa}
                    ${tooltipHTML}
                    <div class="usun" onclick="usunKrzeslo('${k.id}', event)">×</div>
                `;
                div.onmousedown = (e) => startDrag(e, k.id, 'krzeslo');
                plansza.appendChild(div);
            });
        }
        
        // Drag & Drop
        function startDrag(e, id, typ) {
            if (e.target.classList.contains('obrot') || e.target.classList.contains('usun')) return;
            
            przeciagany = {id, typ, el: document.getElementById(id)};
            const rect = przeciagany.el.getBoundingClientRect();
            const parent = document.getElementById('plansza').getBoundingClientRect();
            
            offsetX = e.clientX - rect.left;
            offsetY = e.clientY - rect.top;
            
            document.onmousemove = drag;
            document.onmouseup = stopDrag;
        }
        
        function drag(e) {
            if (!przeciagany) return;
            
            const parent = document.getElementById('plansza').getBoundingClientRect();
            let x = e.clientX - parent.left - offsetX;
            let y = e.clientY - parent.top - offsetY;
            
            // Granice
            x = Math.max(0, Math.min(x, 800 - przeciagany.el.offsetWidth));
            y = Math.max(0, Math.min(y, 600 - przeciagany.el.offsetHeight));
            
            przeciagany.el.style.left = x + 'px';
            przeciagany.el.style.top = y + 'px';
        }
        
        function stopDrag() {
            if (przeciagany) {
                const x = parseFloat(przeciagany.el.style.left);
                const y = parseFloat(przeciagany.el.style.top);
                
                fetch(`/api/przesun/${przeciagany.typ}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: przeciagany.id, x, y})
                });
            }
            przeciagany = null;
            document.onmousemove = null;
            document.onmouseup = null;
        }
        
        // Obracanie
        function startObrot(e, id) {
            e.stopPropagation();
            obracany = {id, el: document.getElementById(id), startX: e.clientX};
            const match = obracany.el.style.transform.match(/rotate\\(([-\\d.]+)deg\\)/);
            obracany.startKat = match ? parseFloat(match[1]) : 0;
            
            document.onmousemove = rotate;
            document.onmouseup = stopObrot;
        }
        
      function rotate(e) {
    if (!obracany) return;
  const delta = (e.clientX - obracany.startX) * 0.5;
    const nowyKat = obracany.startKat + delta;
    obracany.el.style.transform = `rotate(${nowyKat}deg)`;
}
        
        function stopObrot() {
            if (obracany) {
                const match = obracany.el.style.transform.match(/rotate\\(([-\\d.]+)deg\\)/);
                const kat = match ? parseFloat(match[1]) : 0;
                const x = parseFloat(obracany.el.style.left);
                const y = parseFloat(obracany.el.style.top);
                
                fetch('/api/przesun/stolik', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: obracany.id, x, y, kat})
                });
            }
            obracany = null;
            document.onmousemove = null;
            document.onmouseup = null;
        }
        
        // Dodawanie
        function dodajStolik() {
            const dane = {
                nazwa: document.getElementById('stolNazwa').value,
                szer: parseFloat(document.getElementById('stolSzer').value),
                dl: parseFloat(document.getElementById('stolDl').value),
                kolor: document.getElementById('stolKolor').value
            };
            fetch('/api/dodaj/stolik', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(dane)
            }).then(() => odswiez());
        }
        
        function dodajKrzeslo() {
            const dane = {
                nazwa: document.getElementById('krzNazwa').value,
                kolor: document.getElementById('krzKolor').value
            };
            fetch('/api/dodaj/krzeslo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(dane)
            }).then(() => odswiez());
        }
        
        // Usuwanie
        function usunStolik(id, e) {
            e.stopPropagation();
            if (!confirm('Usunąć stolik?')) return;
            fetch('/api/usun/stolik/' + id, {method: 'DELETE'}).then(() => odswiez());
        }
        
        function usunKrzeslo(id, e) {
            e.stopPropagation();
            if (!confirm('Usunąć krzesło? Stracisz historię zamówień!')) return;
            fetch('/api/usun/krzeslo/' + id, {method: 'DELETE'}).then(() => odswiez());
        }
        
        // Menu
        function dodajDanie() {
            const nazwa = document.getElementById('noweNazwa').value;
            const ilosc = parseInt(document.getElementById('noweIlosc').value);
            const kolor = document.getElementById('noweKolor').value;
            if (nazwa && ilosc) {
                fetch('/api/menu', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({nazwa, ilosc, kolor})
                }).then(() => odswiez());
            }
        }
        
        function zmienIlosc(id, zmiana) {
            fetch(`/api/menu/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({zmiana})
            }).then(() => odswiez());
        }
        
        function odswiez() {
            fetch('/api/stan').then(r => r.json()).then(render);
        }
        
        function pokazQR() {
            document.getElementById('qrModal').style.display = 'flex';
        }
        function zamknijQR() {
            document.getElementById('qrModal').style.display = 'none';
        }
        
        socket.on('aktualizacja', odswiez);
    </script>
</body>
</html>
    ''', qr_kod=qr_kod, ip=ip)

@app.route('/kelner')
def kelner():
    return render_template_string('''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kelner - Mapa Sali</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            height: 100vh;
            overflow: hidden;
        }
        
        /* Login */
        .login-screen {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            text-align: center;
            padding: 20px;
        }
        .login-screen h1 { color: #e94560; margin-bottom: 20px; }
        .login-screen input {
            width: 100%;
            max-width: 300px;
            padding: 15px;
            font-size: 1.2rem;
            border-radius: 10px;
            border: 2px solid #e94560;
            background: #16213e;
            color: white;
            text-align: center;
            margin-bottom: 15px;
        }
        .login-screen button {
            width: 100%;
            max-width: 300px;
            padding: 15px;
            font-size: 1.1rem;
            background: #e94560;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
        }
        
        /* App */
        .app-container {
            display: none;
            height: 100vh;
            flex-direction: column;
        }
        
        /* Top bar */
        .top-bar {
            background: #16213e;
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #e94560;
            height: 60px;
        }
        .top-bar h2 { color: #e94560; }
        .kelner-info {
            background: #4ecdc4;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        
        /* Main content */
        .main-content {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        
        /* Mapa z zoomem */
        .mapa-wrapper {
            flex: 1;
            position: relative;
            overflow: hidden;
            background: #0a0a1a;
        }
        .mapa-container {
            width: 100%;
            height: 100%;
            position: relative;
            cursor: grab;
        }
        .mapa-container:active {
            cursor: grabbing;
        }
        .mapa-content {
            position: absolute;
            transform-origin: 0 0;
            transition: transform 0.1s ease-out;
        }
        .plansza-zoom {
            position: relative;
            background: 
                linear-gradient(rgba(78, 205, 196, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(78, 205, 196, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            background-color: #1a1a2e;
            border: 3px solid #e94560;
            box-shadow: 0 0 50px rgba(0,0,0,0.5);
        }
        
        /* Kontrolki zoom */
        .zoom-controls {
            position: absolute;
            bottom: 20px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 100;
        }
        .zoom-btn {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: #4ecdc4;
            color: white;
            font-size: 1.4rem;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            transition: all 0.2s;
        }
        .zoom-btn:hover {
            background: #3dbdb4;
            transform: scale(1.1);
        }
        .zoom-info {
            position: absolute;
            top: 15px;
            left: 20px;
            background: rgba(0,0,0,0.8);
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 0.95rem;
            color: #4ecdc4;
            z-index: 100;
            border: 1px solid #4ecdc4;
        }
        
        /* Krzesła na mapie */
        .krzeslo-map {
            position: absolute;
            width: 45px;
            height: 45px;
            border: 3px solid white;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            transition: all 0.2s;
            transform-origin: center;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .krzeslo-map:hover {
            transform: scale(1.25);
            z-index: 1000;
            box-shadow: 0 0 25px currentColor;
        }
        .krzeslo-map.wybrane {
            box-shadow: 0 0 0 5px #e94560, 0 0 30px #e94560;
            z-index: 500;
            animation: pulse-wybrane 1.5s infinite;
        }
        @keyframes pulse-wybrane {
            0%, 100% { box-shadow: 0 0 0 5px #e94560, 0 0 30px #e94560; }
            50% { box-shadow: 0 0 0 8px #e94560, 0 0 50px #e94560; }
        }
        .krzeslo-map.zajete {
            border-color: #ff6b6b;
            opacity: 0.6;
        }
        .krzeslo-map.zajete::after {
            content: '🔒';
            position: absolute;
            top: -15px;
            right: -15px;
            font-size: 16px;
        }
        .krzeslo-map.ma-zamowienie {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 5px currentColor; }
            50% { box-shadow: 0 0 25px currentColor; }
        }
        .krzeslo-map .licznik {
            position: absolute;
            bottom: -8px;
            right: -8px;
            background: #ff6b6b;
            color: white;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            border: 2px solid white;
        }
        
        /* Stolik na mapie */
        .stolik-map {
            position: absolute;
            border: 3px solid rgba(255,255,255,0.6);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            font-size: 13px;
            opacity: 0.5;
            pointer-events: none;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.2);
        }
        
        /* Panel zamówień */
        .zamowienia-panel {
            width: 380px;
            background: #16213e;
            padding: 20px;
            overflow-y: auto;
            border-left: 3px solid #0f3460;
            transition: transform 0.3s ease;
        }
        .zamowienia-panel.ukryty {
            transform: translateX(100%);
            width: 0;
            padding: 0;
            overflow: hidden;
            border: none;
        }
        
        .krzeslo-info {
            background: #0f3460;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            border-left: 4px solid #e94560;
        }
        .krzeslo-info h3 { color: #e94560; margin-bottom: 8px; font-size: 1.3rem; }
        .krzeslo-info .id { 
            color: #888; 
            font-size: 0.85rem; 
            font-family: monospace;
            background: #1a1a2e;
            padding: 5px 10px;
            border-radius: 5px;
            display: inline-block;
        }
        .krzeslo-info .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-top: 12px;
            font-weight: bold;
        }
        .status.wolne { background: #4ecdc4; color: #1a1a2e; }
        .status.zajete { background: #ff6b6b; }
        .status.twoje { background: #ffa500; color: #1a1a2e; }
        
        /* Menu grid */
        .menu-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 25px;
        }
        .danie-btn {
            padding: 18px;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            color: white;
            position: relative;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        .danie-btn:hover:not(:disabled) { 
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        .danie-btn:active:not(:disabled) { transform: translateY(0); }
        .danie-btn:disabled { 
            opacity: 0.3; 
            cursor: not-allowed;
            filter: grayscale(100%);
        }
        .danie-btn .stan {
            position: absolute;
            top: 6px;
            right: 6px;
            font-size: 0.75rem;
            background: rgba(0,0,0,0.4);
            padding: 3px 8px;
            border-radius: 8px;
        }
        
        /* Historia zamówień */
        .historia-box {
            background: #0f3460;
            border-radius: 12px;
            padding: 20px;
        }
        .historia-box h4 { 
            color: #4ecdc4; 
            margin-bottom: 15px;
            font-size: 1.1rem;
        }
        .zam-item {
            background: #1a1a2e;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 3px solid #4ecdc4;
        }
        .zam-item button {
            background: #ff6b6b;
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .zam-item button:hover { background: #ff4757; transform: scale(1.05); }
        
        .empty-state {
            text-align: center;
            color: #888;
            padding: 60px 20px;
        }
        .empty-state-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        .hint-box {
            background: linear-gradient(135deg, #0f3460, #1a4a7a);
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 20px;
            border-left: 4px solid #4ecdc4;
        }
        .hint-box p { margin: 0; color: #4ecdc4; font-size: 0.95rem; }
        
        /* Przycisk zamknij */
        .btn-zamknij {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            margin-top: 25px;
            transition: all 0.2s;
        }
        .btn-zamknij.podglad {
            background: #4ecdc4;
            color: #1a1a2e;
        }
        .btn-zamknij.edycja {
            background: #666;
            color: white;
        }
        .btn-zamknij:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <!-- Ekran logowania -->
    <div id="loginScreen" class="login-screen">
        <h1>🍽️ System Zamówień</h1>
        <p style="color:#888; margin-bottom:30px;">Podaj swoje imię aby rozpocząć</p>
        <input type="text" id="imieInput" placeholder="Twoje imię" maxlength="20">
        <button onclick="zaloguj()">Wejdź do systemu</button>
    </div>
    
    <!-- Główna aplikacja -->
    <div id="appScreen" class="app-container">
        <div class="top-bar">
            <h2>🗺️ Mapa Sali Restauracyjnej</h2>
            <div style="display:flex; gap:10px; align-items:center;">
                <span class="kelner-info" id="kelnerName">Kelner</span>
                <button onclick="wyloguj()" style="background:#ff6b6b; color:white; border:none; padding:8px 18px; border-radius:20px; cursor:pointer; font-weight:bold;">Wyloguj</button>
            </div>
        </div>
        
        <div class="main-content">
            <!-- Mapa sali z zoomem -->
            <div class="mapa-wrapper" id="mapaWrapper">
                <div class="zoom-info" id="zoomInfo">🔍 100% | Przeciągaj aby przesunąć • Scroll aby przybliżyć</div>
                
                <div class="mapa-container" id="mapaContainer">
                    <div class="mapa-content" id="mapaContent">
                        <div class="plansza-zoom" id="planszaZoom" style="width: 800px; height: 600px;">
                            <!-- Dynamicznie renderowane -->
                        </div>
                    </div>
                </div>
                
                <div class="zoom-controls">
                    <button class="zoom-btn" onclick="zoomIn()" title="Przybliż (+)">+</button>
                    <button class="zoom-btn" onclick="fitToScreen()" title="Dopasuj do ekranu">⌂</button>
                    <button class="zoom-btn" onclick="zoomOut()" title="Oddal (−)">−</button>
                </div>
            </div>
            
            <!-- Panel zamówień -->
            <div class="zamowienia-panel ukryty" id="zamowieniaPanel">
                <div id="zamowieniaContent">
                    <div class="empty-state">
                        <div class="empty-state-icon">🪑</div>
                        <p>Wybierz krzesło z mapy aby rozpocząć obsługę</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let mojeImie = localStorage.getItem('kelnerImie');
        let wybraneKrzeslo = null;
        let zajeteKrzesla = {};
        let salaData = null;
        let menuData = [];
        const socket = io();
        
        // Zoom i Pan
        let scale = 1;
        let panX = 0;
        let panY = 0;
        let isPanning = false;
        let startPanX = 0;
        let startPanY = 0;
        
        const mapaContainer = document.getElementById('mapaContainer');
        const mapaContent = document.getElementById('mapaContent');
        const zoomInfo = document.getElementById('zoomInfo');
        
        function updateTransform() {
            mapaContent.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
            zoomInfo.textContent = `🔍 ${Math.round(scale * 100)}% | Przeciągaj aby przesunąć • Scroll aby przybliżyć`;
        }
        
        function zoomIn() {
            scale = Math.min(scale * 1.25, 4);
            updateTransform();
        }
        
        function zoomOut() {
            scale = Math.max(scale / 1.25, 0.2);
            updateTransform();
        }
        
        function resetZoom() {
            scale = 1;
            panX = 0;
            panY = 0;
            updateTransform();
        }
        
        function fitToScreen() {
            const wrapper = document.getElementById('mapaWrapper');
            const plansza = document.getElementById('planszaZoom');
            const scaleX = (wrapper.clientWidth - 40) / plansza.clientWidth;
            const scaleY = (wrapper.clientHeight - 40) / plansza.clientHeight;
            scale = Math.min(scaleX, scaleY, 1.5);
            panX = (wrapper.clientWidth - plansza.clientWidth * scale) / 2;
            panY = (wrapper.clientHeight - plansza.clientHeight * scale) / 2;
            updateTransform();
        }
        
        // Pan (przesuwanie)
        mapaContainer.addEventListener('mousedown', (e) => {
            if (e.target.closest('.krzeslo-map') || e.target.closest('.zoom-controls')) return;
            isPanning = true;
            startPanX = e.clientX - panX;
            startPanY = e.clientY - panY;
            mapaContainer.style.cursor = 'grabbing';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            panX = e.clientX - startPanX;
            panY = e.clientY - startPanY;
            updateTransform();
        });
        
        document.addEventListener('mouseup', () => {
            isPanning = false;
            mapaContainer.style.cursor = 'grab';
        });
        
        // Zoom kółkiem myszy
        mapaContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.85 : 1.15;
            const newScale = Math.max(0.2, Math.min(4, scale * delta));
            
            const rect = mapaContainer.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            panX = mouseX - (mouseX - panX) * (newScale / scale);
            panY = mouseY - (mouseY - panY) * (newScale / scale);
            scale = newScale;
            
            updateTransform();
        });
        
        // Inicjalizacja
        if (mojeImie) {
            pokazApp();
            socket.emit('zaloguj', {imie: mojeImie});
        }
        
        function zaloguj() {
            const imie = document.getElementById('imieInput').value.trim();
            if (imie.length < 2) return alert('Wpisz przynajmniej 2 znaki!');
            mojeImie = imie;
            localStorage.setItem('kelnerImie', imie);
            socket.emit('zaloguj', {imie: imie});
            pokazApp();
        }
        
        function wyloguj() {
            if (wybraneKrzeslo) {
                socket.emit('zwolnij_krzeslo', {krzeslo_id: wybraneKrzeslo.id, kelner: mojeImie});
            }
            localStorage.removeItem('kelnerImie');
            socket.emit('wyloguj', {imie: mojeImie});
            location.reload();
        }
        
        function pokazApp() {
            document.getElementById('loginScreen').style.display = 'none';
            document.getElementById('appScreen').style.display = 'flex';
            document.getElementById('kelnerName').textContent = mojeImie;
            odswiez();
            setTimeout(fitToScreen, 100);
        }
        
        function odswiez() {
            Promise.all([
                fetch('/api/sala').then(r => r.json()),
                fetch('/api/menu').then(r => r.json())
            ]).then(([sala, menu]) => {
                salaData = sala;
                menuData = menu;
                renderMapa();
                if (wybraneKrzeslo) {
                    const aktualne = sala.krzesla.find(k => k.id === wybraneKrzeslo.id);
                    if (aktualne) {
                        wybraneKrzeslo = aktualne;
                        renderPanel();
                    }
                }
            });
        }
        
        function renderMapa() {
            const plansza = document.getElementById('planszaZoom');
            plansza.innerHTML = '';
            
            // Stoliki
            salaData.stoliki.forEach(s => {
                const div = document.createElement('div');
                div.className = 'stolik-map';
                div.style.width = (s.szerokosc * 50) + 'px';
                div.style.height = (s.dlugosc * 50) + 'px';
                div.style.left = s.poz_x + 'px';
                div.style.top = s.poz_y + 'px';
                div.style.transform = `rotate(${s.kat}deg)`;
                div.style.background = s.kolor;
                div.textContent = s.nazwa;
                plansza.appendChild(div);
            });
            
            // Krzesła
            salaData.krzesla.forEach(k => {
                const btn = document.createElement('button');
                const jestZajete = zajeteKrzesla[k.id] && zajeteKrzesla[k.id] !== mojeImie;
                const mojeZajete = zajeteKrzesla[k.id] === mojeImie;
                const sumaZam = k.zamowienia.reduce((s, z) => s + z.ilosc, 0);
                
                btn.className = 'krzeslo-map' + 
                    (mojeZajete ? ' wybrane' : '') +
                    (jestZajete ? ' zajete' : '') +
                    (sumaZam > 0 ? ' ma-zamowienie' : '');
                btn.id = 'krz_' + k.id;
                btn.style.left = k.poz_x + 'px';
                btn.style.top = k.poz_y + 'px';
                btn.style.transform = `rotate(${k.kat}deg)`;
                btn.style.backgroundColor = k.kolor;
                btn.innerHTML = `
                    ${k.nazwa}
                    ${sumaZam > 0 ? `<span class="licznik">${sumaZam}</span>` : ''}
                `;
                
                btn.onclick = (e) => {
                    e.stopPropagation();
                    kliknijKrzeslo(k);
                };
                
                plansza.appendChild(btn);
            });
        }
        
        function kliknijKrzeslo(krzeslo) {
            const jestZajete = zajeteKrzesla[krzeslo.id] && zajeteKrzesla[krzeslo.id] !== mojeImie;
            
            if (jestZajete) {
                wybraneKrzeslo = krzeslo;
                renderPanel(true);
                document.getElementById('zamowieniaPanel').classList.remove('ukryty');
                return;
            }
            
            if (wybraneKrzeslo && wybraneKrzeslo.id !== krzeslo.id) {
                socket.emit('zwolnij_krzeslo', {krzeslo_id: wybraneKrzeslo.id, kelner: mojeImie});
            }
            
            wybraneKrzeslo = krzeslo;
            socket.emit('zajmij_krzeslo', {krzeslo_id: krzeslo.id, kelner: mojeImie});
            
            document.getElementById('zamowieniaPanel').classList.remove('ukryty');
            renderMapa();
            renderPanel(false);
        }
        
        function renderPanel(tylkoPodglad = false) {
            const panel = document.getElementById('zamowieniaContent');
            const k = wybraneKrzeslo;
            const jestZajete = zajeteKrzesla[k.id] && zajeteKrzesla[k.id] !== mojeImie;
            const mojeZajete = zajeteKrzesla[k.id] === mojeImie;
            
            let statusText = '✅ Wolne - kliknij aby zająć';
            let statusClass = 'wolne';
            if (mojeZajete) {
                statusText = '🔶 Twoje - możesz dodawać zamówienia';
                statusClass = 'twoje';
            } else if (jestZajete) {
                statusText = `🔒 Zajęte przez: ${zajeteKrzesla[k.id]}`;
                statusClass = 'zajete';
            }
            
            const grupy = {};
            k.zamowienia.forEach(z => {
                if (!grupy[z.danie]) grupy[z.danie] = {ilosc: 0, items: []};
                grupy[z.danie].ilosc += z.ilosc;
                grupy[z.danie].items.push(z);
            });
            
            let historiaHTML = '';
            if (k.zamowienia.length > 0) {
                historiaHTML = `
                    <div class="historia-box">
                        <h4>📝 Zamówienia (${k.zamowienia.length} pozycji):</h4>
                        ${Object.entries(grupy).map(([danie, info]) => `
                            <div class="zam-item">
                                <div>
                                    <strong>${danie}</strong> × ${info.ilosc}
                                    <br><small style="color:#888;">${info.items[0].kelner}</small>
                                </div>
                                ${!tylkoPodglad ? `
                                    <button onclick="usunZamowienie('${info.items[0].id}')">Usuń</button>
                                ` : '<span style="color:#ff6b6b; font-size:1.2rem;">🔒</span>'}
                            </div>
                        `).join('')}
                    </div>
                `;
            }
            
            let menuHTML = '';
            if (!tylkoPodglad) {
                menuHTML = `
                    <div class="menu-grid">
                        ${menuData.map(d => `
                            <button class="danie-btn" 
                                    style="background:${d.kolor};"
                                    onclick="dodajZamowienie('${k.id}', '${d.nazwa}')"
                                    ${d.ilosc <= 0 ? 'disabled' : ''}>
                                ${d.nazwa}
                                <span class="stan">${d.ilosc} szt.</span>
                            </button>
                        `).join('')}
                    </div>
                `;
            } else {
                menuHTML = `
                    <div class="hint-box">
                        <p>🔒 <strong>Tryb podglądu</strong><br>To krzesło jest aktualnie obsługiwane przez innego kelnera. Możesz tylko przeglądać zamówienia.</p>
                    </div>
                `;
            }
            
            panel.innerHTML = `
                <div class="krzeslo-info">
                    <h3>🪑 ${k.nazwa}</h3>
                    <div class="id">ID: ${k.id}</div>
                    <span class="status ${statusClass}">${statusText}</span>
                </div>
                
                ${menuHTML}
                ${historiaHTML}
                
                <button class="btn-zamknij ${tylkoPodglad ? 'podglad' : 'edycja'}" onclick="zamknijPanel()">
                    ${tylkoPodglad ? '✓ Zamknij podgląd' : '✓ Zamknij i zwolnij krzesło'}
                </button>
            `;
        }
        
        function dodajZamowienie(kid, danie) {
            fetch('/api/zamowienie', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    krzeslo_id: kid,
                    danie: danie,
                    kelner: mojeImie
                })
            }).then(r => r.json()).then(resp => {
                if (resp.ok) {
                    odswiez();
                } else {
                    alert('Błąd: ' + (resp.error || 'Brak w magazynie'));
                }
            });
        }
        
        function usunZamowienie(zamId) {
            if (!confirm('Usunąć to zamówienie?')) return;
            fetch('/api/zamowienie/usun/' + zamId, {method: 'DELETE'})
                .then(() => odswiez());
        }
        
        function zamknijPanel() {
            if (wybraneKrzeslo) {
                socket.emit('zwolnij_krzeslo', {krzeslo_id: wybraneKrzeslo.id, kelner: mojeImie});
            }
            wybraneKrzeslo = null;
            document.getElementById('zamowieniaPanel').classList.add('ukryty');
            renderMapa();
        }
        
        // Socket events
        socket.on('aktualizacja', odswiez);
        
        socket.on('krzeslo_zajete', (data) => {
            zajeteKrzesla[data.krzeslo_id] = data.kelner;
            renderMapa();
            if (wybraneKrzeslo && wybraneKrzeslo.id === data.krzeslo_id && data.kelner !== mojeImie) {
                renderPanel(true);
            }
        });
        
        socket.on('krzeslo_wolne', (data) => {
            delete zajeteKrzesla[data.krzeslo_id];
            renderMapa();
        });
        
        socket.on('zajete_krzesla', (data) => {
            zajeteKrzesla = data || {};
            renderMapa();
        });
    </script>
</body>
</html>
    ''')

# API
@app.route('/api/stan')
def api_stan():
    return jsonify({
        'menu': get_menu(),
        'kelnerzy': get_kelnerzy(),
        'sala': pobierz_sale()
    })

@app.route('/api/sala')
def api_sala():
    return jsonify(pobierz_sale())

@app.route('/api/menu')
def api_menu():
    return jsonify(get_menu())

@app.route('/api/menu', methods=['POST'])
def dodaj_menu():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO menu (nazwa, ilosc, kolor) VALUES (?, ?, ?)",
              (data['nazwa'], data['ilosc'], data['kolor']))
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

@app.route('/api/menu/<int:id>', methods=['PUT'])
def edytuj_menu(id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE menu SET ilosc = MAX(0, ilosc + ?) WHERE id=?", (data['zmiana'], id))
    conn.commit()
    conn.close()
    socketio.emit('aktualizacja', broadcast=True)
    return jsonify({'ok': True})

# Plansza - stoliki
@app.route('/api/dodaj/stolik', methods=['POST'])
def api_dodaj_stolik():
    d = request.json
    dodaj_stolik(d['nazwa'], d['szer'], d['dl'], 50, 50, 0, d.get('kolor', '#4ecdc4'))
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

@app.route('/api/usun/stolik/<id>', methods=['DELETE'])
def api_usun_stolik(id):
    usun_stolik(id)
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

# Plansza - krzesła
@app.route('/api/dodaj/krzeslo', methods=['POST'])
def api_dodaj_krzeslo():
    d = request.json
    dodaj_krzeslo(d.get('nazwa', 'Krzesło'), 100, 100, 0, d.get('kolor', '#ffa500'))
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

@app.route('/api/usun/krzeslo/<id>', methods=['DELETE'])
def api_usun_krzeslo(id):
    usun_krzeslo(id)
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

# Przesuwanie
@app.route('/api/przesun/<typ>', methods=['POST'])
def api_przesun(typ):
    d = request.json
    if typ == 'stolik':
        przesun_stolik(d['id'], d['x'], d['y'], d.get('kat'))
    else:
        przesun_krzeslo(d['id'], d['x'], d['y'], d.get('kat'))
    socketio.emit('aktualizacja')
    return jsonify({'ok': True})

# Zamówienia
@app.route('/api/zamowienie', methods=['POST'])
def api_zamowienie():
    d = request.json
    
    # Sprawdź dostępność
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ilosc FROM menu WHERE nazwa=?", (d['danie'],))
    wynik = c.fetchone()
    
    if not wynik or wynik[0] <= 0:
        conn.close()
        return jsonify({'ok': False, 'error': 'Brak w magazynie'})
    
    # Dodaj zamówienie
    dodaj_zamowienie_krzeslo(d['krzeslo_id'], d['danie'], d['kelner'])
    
    # Zmniejsz stan
    c.execute("UPDATE menu SET ilosc = ilosc - 1 WHERE nazwa=?", (d['danie'],))
    conn.commit()
    conn.close()
    
    socketio.emit('aktualizacja') 
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

@socketio.on('wyloguj')
def handle_wyloguj(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE kelnerzy SET aktywny=0 WHERE imie=?", (data['imie'],))
    conn.commit()
    conn.close()

# Globalny słownik zajętych krzeseł
zajete_krzesla = {}  # krzeslo_id -> kelner_imie

@socketio.on('zajmij_krzeslo')
def handle_zajmij(data):
    krzeslo_id = data['krzeslo_id']
    kelner = data['kelner']
    
    # Sprawdź czy nie zajęte przez innego
    if krzeslo_id in zajete_krzesla and zajete_krzesla[krzeslo_id] != kelner:
        emit('blad', {'msg': 'Krzesło zajęte przez innego kelnera'})
        return
    
    zajete_krzesla[krzeslo_id] = kelner
    emit('krzeslo_zajete', {'krzeslo_id': krzeslo_id, 'kelner': kelner}, broadcast=True)
    emit('zajete_krzesla', zajete_krzesla)  # wyślij aktualną listę do klienta

@socketio.on('zwolnij_krzeslo')
def handle_zwolnij(data):
    krzeslo_id = data['krzeslo_id']
    kelner = data['kelner']
    
    if krzeslo_id in zajete_krzesla and zajete_krzesla[krzeslo_id] == kelner:
        del zajete_krzesla[krzeslo_id]
        emit('krzeslo_wolne', {'krzeslo_id': krzeslo_id}, broadcast=True)

@socketio.on('pobierz_zajete')
def handle_pobierz_zajete():
    emit('zajete_krzesla', zajete_krzesla)

@socketio.on('connect')
def handle_connect():
    # Wyślij aktualną listę zajętych przy połączeniu
    emit('zajete_krzesla', zajete_krzesla)

if __name__ == '__main__':
    init_db()
    
    IP = get_ip()
    PORT = 5000
    
    print(f"\n{'='*60}")
    print(f"🍽️  SYSTEM ZAMÓWIEŃ - PLANSZA SALI")
    print(f"{'='*60}")
    print(f"\n🖥️  Admin (plansza): http://{IP}:{PORT}")
    print(f"📱 Kelner: http://{IP}:{PORT}/kelner")
    print(f"{'='*60}\n")
    
    threading.Timer(2.0, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)