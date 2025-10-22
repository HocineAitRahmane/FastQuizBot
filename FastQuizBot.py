import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import pyautogui
import pytesseract
import time
from groq import Groq
import threading
from pynput import mouse


# --- CONFIGURATION TESSERACT ---
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- VARIABLES GLOBALES ---
client = None
game_region = None
auto_mode_active = False
last_captured_text = ""
captured_position = None


# --- FONCTIONS UTILITAIRES ---
def log_output(message):
    """Affiche un message dans la zone de texte."""
    window.after(0, lambda: [
        output_text.insert(tk.END, message + "\n"),
        output_text.see(tk.END)
    ])


def on_click_capture(x, y, button, pressed):
    """Callback de pynput : capture le premier clic gauche et arrête l'écoute."""
    global captured_position
    if pressed and button == mouse.Button.left:
        captured_position = (x, y)
        return False


def wait_for_click(instruction_title):
    """Affiche un message et attend le clic de l'utilisateur sur l'écran."""
    global captured_position
    captured_position = None
    window.withdraw()
    messagebox.showinfo(
        instruction_title,
        f"🎯 {instruction_title} : Clique sur le coin du quiz pour capturer la position.\n\nClique 'OK' pour commencer."
    )
    with mouse.Listener(on_click=on_click_capture) as listener:
        listener.join()
    window.deiconify()
    return captured_position


# --- FONCTIONS PRINCIPALES ---
def select_region():
    global game_region

    pos1 = wait_for_click("SÉLECTION - COIN SUPÉRIEUR GAUCHE")
    if pos1 is None:
        messagebox.showerror("Erreur", "Clic non capturé.")
        return
    x1, y1 = pos1
    messagebox.showinfo("Capture", f"Position 1 capturée : ({x1}, {y1})")

    pos2 = wait_for_click("SÉLECTION - COIN INFÉRIEUR DROIT")
    if pos2 is None:
        messagebox.showerror("Erreur", "Clic non capturé.")
        return
    x2, y2 = pos2

    if x2 <= x1 or y2 <= y1:
        messagebox.showerror("Erreur", "Zone invalide.")
        game_region = None
        zone_label.config(text="Zone du quiz : sélection invalide", foreground="#DC3545")
        return

    width, height = x2 - x1, y2 - y1
    game_region = (x1, y1, width, height)
    zone_label.config(text=f"Zone sélectionnée : {game_region}", foreground="#28A745")
    messagebox.showinfo("✅ Zone définie", f"Zone du quiz : {game_region}")


def capture_game_text():
    if not game_region:
        return "⚠️ Zone non définie !"
    screenshot = pyautogui.screenshot(region=game_region)
    text = pytesseract.image_to_string(screenshot, lang="eng+fra", config='--psm 6')
    return text.strip()


def analyze_question_with_ai(text):
    if not text:
        return "⚠️ Aucun texte détecté. Réessaye."

    prompt = f"""
Tu es un expert en quiz. Voici une question avec quatre propositions :
{text}

Lis bien la question et les propositions, puis donne uniquement la bonne réponse (sans explication).
"""
    try:
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-instruct-0905",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Erreur IA : {e}"


def run_bot():
    global last_captured_text

    if not game_region:
        log_output("⚠️ Zone manquante. Sélectionne la zone du quiz d'abord.")
        return

    if not auto_mode_active:
        output_text.delete("1.0", tk.END)

    log_output("📸 Capture du quiz...")
    text = capture_game_text()

    if not text or text.isspace():
        if not auto_mode_active:
            log_output("⚠️ Aucun texte détecté dans la zone !")
        return

    if auto_mode_active and text == last_captured_text:
        return

    last_captured_text = text

    log_output(f"\n--- Nouvelle Question ---\n")
    log_output(f"🧾 Texte détecté :\n{text}\n")
    log_output("🤖 Analyse en cours...\n")

    def ai_thread_execution():
        try:
            result = analyze_question_with_ai(text)
            log_output("✅ Réponse trouvée : " + result + "\n")
        except Exception as e:
            log_output(f"❌ Erreur inattendue : {e}")

    threading.Thread(target=ai_thread_execution, daemon=True).start()


# --- MODE AUTOMATIQUE ---
def start_auto_mode():
    global auto_mode_active, last_captured_text

    if auto_mode_active:
        messagebox.showwarning("Mode Auto", "Déjà actif !")
        return
    if not game_region:
        messagebox.showwarning("Zone manquante", "Sélectionne la zone du quiz d'abord.")
        return

    auto_mode_active = True
    last_captured_text = ""
    output_text.delete("1.0", tk.END)
    log_output("--- 🟢 MODE AUTO DÉMARRÉ (5s d'intervalle) ---")

    btn_start_auto.state(['disabled'])
    btn_stop_auto.state(['!disabled'])
    btn_run_manual.state(['disabled'])
    btn_refresh_manual.state(['disabled'])

    auto_mode_loop()


def auto_mode_loop():
    if auto_mode_active:
        threading.Thread(target=run_bot, daemon=True).start()
        window.after(5000, auto_mode_loop)


def stop_auto_mode():
    global auto_mode_active
    if not auto_mode_active:
        messagebox.showwarning("Mode Auto", "Pas actif.")
        return
    auto_mode_active = False
    log_output("--- 🔴 MODE AUTO ARRÊTÉ ---")
    btn_start_auto.state(['!disabled'])
    btn_stop_auto.state(['disabled'])
    btn_run_manual.state(['!disabled'])
    btn_refresh_manual.state(['!disabled'])


def stop_bot():
    window.destroy()


# --- FENÊTRE PRINCIPALE ---
window = tk.Tk()
window.title("🎯 Quiz AutoBot - IA Quiz Solver (Public Version)")
window.geometry("640x650")
window.resizable(False, False)
window.attributes('-topmost', True)
window.configure(bg='#F0F0F0')

style = ttk.Style()
style.theme_use('clam')
style.configure('TButton', font=('Arial', 10))
style.configure('Header.TLabel', font=('Arial', 16, 'bold'))

# --- FENÊTRE DE CONNEXION API ---
api_key = simpledialog.askstring(
    "Clé API Groq",
    "🔑 Entrez votre clé API Groq (commence par gsk_...) :",
    show="*"
)

if not api_key or not api_key.startswith("gsk_"):
    messagebox.showerror("Erreur", "Clé API invalide. Relancez l'application.")
    window.destroy()
    exit()

try:
    client = Groq(api_key=api_key)
except Exception as e:
    messagebox.showerror("Erreur", f"Impossible d'initialiser Groq : {e}")
    window.destroy()
    exit()

# --- INTERFACE ---
ttk.Label(window, text="🤖 Quiz AutoBot - IA Quiz Solver", style='Header.TLabel').pack(pady=15)
zone_label = ttk.Label(window, text="Zone du quiz : non sélectionnée", foreground="#DC3545")
zone_label.pack(pady=5)

frame_config = ttk.Frame(window, padding="10")
frame_config.pack(pady=10)
ttk.Button(frame_config, text="🎯 Sélectionner la zone (Clic Écran)", command=select_region, width=35).grid(row=0, column=0, padx=5, pady=5)
ttk.Button(frame_config, text="🛑 Quitter", command=stop_bot, width=20).grid(row=0, column=1, padx=5, pady=5)

ttk.Separator(window, orient='horizontal').pack(fill='x', padx=20, pady=10)
ttk.Label(window, text="Mode Manuel", font=("Arial", 12, "bold")).pack()
frame_manuel = ttk.Frame(window, padding="10")
frame_manuel.pack(pady=5)

btn_run_manual = ttk.Button(frame_manuel, text="🚀 Démarrer (Manuel)", command=lambda: threading.Thread(target=run_bot, daemon=True).start(), width=25)
btn_run_manual.grid(row=0, column=0, padx=5, pady=5)
btn_refresh_manual = ttk.Button(frame_manuel, text="🔁 Relancer (Manuel)", command=lambda: threading.Thread(target=run_bot, daemon=True).start(), width=25)
btn_refresh_manual.grid(row=0, column=1, padx=5, pady=5)

ttk.Separator(window, orient='horizontal').pack(fill='x', padx=20, pady=10)
ttk.Label(window, text="Mode Automatique (5s)", font=("Arial", 12, "bold")).pack()

frame_auto = ttk.Frame(window, padding="10")
frame_auto.pack(pady=5)
btn_start_auto = ttk.Button(frame_auto, text="🌟 Lancer Auto Mode", command=start_auto_mode, width=25)
btn_start_auto.grid(row=0, column=0, padx=5, pady=5)
btn_stop_auto = ttk.Button(frame_auto, text="🛑 Stop Auto Mode", command=stop_auto_mode, width=25, state='disabled')
btn_stop_auto.grid(row=0, column=1, padx=5, pady=5)

ttk.Label(window, text="📜 Sortie du bot :", font=("Arial", 12, "bold")).pack(pady=5)
frame_output = ttk.Frame(window)
frame_output.pack(padx=10, pady=5)

scrollbar = ttk.Scrollbar(frame_output)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
output_text = tk.Text(frame_output, height=15, width=75, wrap="word", font=("Consolas", 10),
                      yscrollcommand=scrollbar.set, relief=tk.FLAT, bd=1)
output_text.pack(side=tk.LEFT, fill=tk.BOTH)
scrollbar.config(command=output_text.yview)

window.mainloop()
