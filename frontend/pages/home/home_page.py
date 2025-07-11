import json
import tkinter as tk
from tkinter import ttk, messagebox
import time

from client_network import send_to_server, receive_from_server, connect_to_server, close_connections
from .home_actions import HomeActions
from .home_widgets import HomeWidgets, HomeScrolling
from .request_manager import RequestManager

# Costanti per stili
CARD_FRAME_STYLE = "Card.TFrame"
ACCENT_BUTTON_STYLE = "Accent.TButton"

# Costanti per stati richieste
STATO_IN_ATTESA = "in_attesa"

# Costanti per messaggi di errore
ERROR_SERVER_RESPONSE = "Errore nella risposta del server"
ERROR_CONNECTION = "Errore di connessione o BrokenPipe"

class HomePage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg="black")
        self.current_view = "waiting_games"
        
        # Cache per evitare aggiornamenti non necessari
        self._last_games_data = None
        
        # Inizializza i manager
        self.actions = HomeActions(self)
        self.widgets = HomeWidgets(self)
        self.scrolling = HomeScrolling(self)
        self.request_manager = RequestManager(self)
        # NON creiamo più il server_polling qui - è centralizzato nel MainApp
        
        # Configura il layout a griglia della pagina principale
        self.rowconfigure(0, weight=0)  # Navbar - fisso
        self.rowconfigure(1, weight=0)  # Separatore
        self.rowconfigure(2, weight=0)  # Sezione nuova partita - ridotto
        self.rowconfigure(3, weight=0)  # Separatore
        self.rowconfigure(4, weight=0)  # Pulsanti di navigazione
        self.rowconfigure(5, weight=1)  # Sezione contenuto dinamico - tutto lo spazio rimanente
        self.columnconfigure(0, weight=1)

        # Navbar
        navbar = ttk.Frame(self, style="TFrame")
        navbar.grid(row=0, column=0, sticky="nsew")

        navbar.columnconfigure(0, weight=0)
        navbar.columnconfigure(1, weight=1)

        navbar_label = ttk.Label(navbar, text="Tris", justify="center", style="Title.TLabel")
        navbar_label.grid(row=0, column=1, pady=(10, 5), sticky="n")

        # Separatore
        separator = ttk.Separator(self, orient="horizontal")
        separator.grid(row=1, column=0, sticky="ew", padx=(30,30), pady=(0, 10))

        # Sezione nuova partita
        section1 = ttk.Frame(self, style="TFrame")
        section1.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 5))

        section1.columnconfigure(0, weight=1)

        self.welcome_label = ttk.Label(
            section1, 
            text="Benvenuto", 
            style="Title.TLabel", 
            justify="center",
            anchor="center"
        )
        self.welcome_label.pack(pady=(10, 5), padx=(30,0))

        button_new_game = ttk.Button(section1, text="Nuova partita", style=ACCENT_BUTTON_STYLE, command=self.actions.new_game)
        button_new_game.pack(pady=(5,10), padx=(30,0))

        # Separatore
        separator = ttk.Separator(self, orient="horizontal")
        separator.grid(row=3, column=0, sticky="ew", padx=(30,30), pady=(0, 5))

        # Pulsanti di navigazione
        nav_frame = ttk.Frame(self, style="TFrame")
        nav_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(5, 10))
        nav_frame.columnconfigure(0, weight=1)
        nav_frame.columnconfigure(1, weight=1)
        nav_frame.columnconfigure(2, weight=1)

        self.btn_waiting = ttk.Button(nav_frame, text="Partite in attesa", 
                                     command=lambda: self.change_view("waiting_games"))
        self.btn_waiting.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_received = ttk.Button(nav_frame, text="Richieste ricevute", 
                                      command=lambda: self.change_view("received_requests"))
        self.btn_received.grid(row=0, column=1, padx=5, sticky="ew")

        self.btn_sent = ttk.Button(nav_frame, text="Richieste effettuate", 
                                  command=lambda: self.change_view("sent_requests"))
        self.btn_sent.grid(row=0, column=2, padx=5, sticky="ew")

        # Sezione contenuto dinamico
        self.content_frame = ttk.Frame(self, style="TFrame")
        self.content_frame.grid(row=5, column=0, sticky="nsew", padx=20, pady=(0, 5))
        
        # Configura il grid del content_frame per espansione
        self.content_frame.rowconfigure(1, weight=1)  # Per il scroll_frame
        self.content_frame.columnconfigure(0, weight=1)
        
        # Label del titolo della sezione
        self.section_title = ttk.Label(self.content_frame, text="Partite in attesa...", style="TLabel")
        self.section_title.grid(row=0, column=0, padx=(10, 0), pady=(0, 5), sticky="w")

        # Frame per scrollbar e canvas con sfondo nero
        self.scroll_frame = ttk.Frame(self.content_frame, style="TFrame")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        self.content_container = ttk.Frame(self.scroll_frame, style="TFrame")
        self.content_container.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(self.scroll_frame, highlightthickness=0, bg="black", bd=0, height=250)
        self.scrollbar = ttk.Scrollbar(self.scroll_frame, orient="vertical", command=self.canvas.yview)
        self.content_container = ttk.Frame(self.canvas, style="TFrame")
        
        # # Configura la scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # # Pack scrollbar e canvas - mostra sempre la scrollbar
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # # Crea la finestra nel canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_container, anchor="nw")
        
        # # Bind eventi per aggiornare la scrollregion
        self.content_container.bind('<Configure>', self.scrolling.on_frame_configure)
        
        # # Abilita lo scroll con la rotella del mouse
        self.canvas.bind("<MouseWheel>", self.scrolling.on_mousewheel)

        # Aggiorna lo stile del pulsante attivo
        self.update_button_styles()

    def update_button_styles(self):
        """Aggiorna lo stile dei pulsanti per evidenziare quello attivo"""
        # Reset tutti i pulsanti allo stile normale
        self.btn_waiting.configure(style="TButton")
        self.btn_received.configure(style="TButton")
        self.btn_sent.configure(style="TButton")
        
        # Evidenzia il pulsante attivo
        if self.current_view == "waiting_games":
            self.btn_waiting.configure(style=ACCENT_BUTTON_STYLE)
        elif self.current_view == "received_requests":
            self.btn_received.configure(style=ACCENT_BUTTON_STYLE)
        elif self.current_view == "sent_requests":
            self.btn_sent.configure(style=ACCENT_BUTTON_STYLE)

    def change_view(self, view_type):
        """Cambia la vista corrente"""
        # Reset cache quando si cambia vista per forzare aggiornamento
        if view_type != self.current_view and view_type == "waiting_games":
            self._last_games_data = None
            
        self.current_view = view_type
        self.update_button_styles()
        
        # Aggiorna il titolo e il contenuto
        if view_type == "waiting_games":
            self.section_title.config(text="Partite in attesa...")
            self.update_waiting_games()
        elif view_type == "received_requests":
            self.section_title.config(text="Richieste ricevute...")
            self.actions.upload_received_requests()
            self.update_received_requests()
        elif view_type == "sent_requests":
            self.section_title.config(text="Richieste effettuate...")
            self.actions.upload_send_requests()
            self.update_sent_requests()

    def periodic_update_content(self):
        # Controlla se l'applicazione è ancora attiva prima di continuare
        try:
            if not self.winfo_exists() or not hasattr(self, 'controller') or not self.controller.winfo_exists():
                return
        except Exception:
            return
            
        self._content_after_id = self.after(3000, self.periodic_update_content)
        if self.current_view == "waiting_games":
             self.update_waiting_games()

    def stop_periodic_update_content(self):
        """Ferma l'aggiornamento periodico"""
        if hasattr(self, '_content_after_id'):
            self.after_cancel(self._content_after_id)
            del self._content_after_id

    def update_data(self):
        nickname = self.controller.shared_data.get('nickname', "Utente")
        
        # Gestione nickname su una sola riga con troncamento se necessario
        if len(nickname) > 15:
            # Per nickname lunghi, tronca con ...
            display_name = f"Benvenuto, {nickname[:12]}...!"
        else:
            # Per nickname normali, mantiene tutto su una riga
            display_name = f"Benvenuto, {nickname}!"
            
        self.welcome_label.config(text=display_name)
        self.change_view(self.current_view)
        self.periodic_update_content()
        
        
        # Avvia il polling del server tramite il manager centralizzato
        self.controller.start_global_polling()


    def __del__(self):
        """Cleanup quando l'oggetto viene distrutto"""
        # Non gestiamo più il server_polling qui - è centralizzato
        self.stop_periodic_update_content()

    def clear_content(self):
        """Pulisce il contenuto del container con protezione"""
        try:
            if hasattr(self, 'content_container') and self.content_container.winfo_exists():
                for widget in self.content_container.winfo_children():
                    if widget.winfo_exists():
                        widget.destroy()
        except tk.TclError as e:
            print(f"Errore durante clear_content: {e}")
        except Exception as e:
            print(f"Errore generico in clear_content: {e}")

    def _games_data_changed(self, new_games):
        """Verifica se i dati delle partite sono cambiati rispetto alla cache"""
        if self._last_games_data is None:
            return True
        
        # Verifica se il numero di partite è cambiato
        if len(self._last_games_data) != len(new_games):
            return True
        
        # Crea dizionari ordinati per confronto completo di tutti i campi
        def normalize_game_data(games):
            """Normalizza i dati delle partite per il confronto"""
            normalized = []
            for game in games:
                normalized_game = {
                    'id_partita': game.get('id_partita', 0),
                    'proprietario': game.get('proprietario', ''),
                }
                normalized.append(normalized_game)
            # Ordina per id_partita per confronto consistente
            return sorted(normalized, key=lambda x: x['id_partita'])
        
        old_normalized = normalize_game_data(self._last_games_data)
        new_normalized = normalize_game_data(new_games)
        
        # Confronta le strutture dati complete
        return old_normalized != new_normalized

    def update_waiting_games(self):
        """Aggiorna la lista delle partite in attesa solo se i dati sono cambiati"""
        # Controlla se l'applicazione è ancora attiva
        try:
            if not self.winfo_exists() or not hasattr(self, 'controller') or not self.controller.winfo_exists():
                return
        except Exception:
            return
            
        try:
            response = send_to_server("/waiting_games", {})
            
            # Controlla se la risposta è vuota o None
            if not response or response.strip() == "":
                games = []
            else:
                try:
                    data = json.loads(response)
                    
                    # ✅ CONTROLLA SE LA RISPOSTA È UNA RICHIESTA PUSH INVECE CHE PARTITE
                    if data.get("path") == "/new_request":
                        # Gestisci come richiesta push
                        new_request = {
                            'game_id': data.get('game_id'),
                            'player_id': data.get('player_id'),
                            'mittente': data.get('player_name', 'Sconosciuto'),
                        }
                        self.request_manager.add_received_request(new_request)
                        
                        # Riprova a richiedere le partite
                        response = send_to_server("/waiting_games", {})
                        if not response or response.strip() == "":
                            data = {"partite": []}
                        else:
                            data = json.loads(response)
                    
                    games = data.get("partite", [])
                    
                    # ✅ CONTROLLO CACHE: Aggiorna UI solo se i dati sono cambiati
                    if not self._games_data_changed(games):
                        return
                    
                    # Aggiorna la cache
                    self._last_games_data = games.copy() if games else []
                                       
                except json.JSONDecodeError as e:
                    print(f"Errore parsing JSON: {e}")
                    games = []
                
        except ConnectionError as e:
            print(f"Errore di connessione: {e}")
            games = []
            # Controlla se l'applicazione è ancora attiva prima di mostrare messagebox
            try:
                if self.winfo_exists() and hasattr(self, 'controller') and self.controller.winfo_exists():
                    # Mostra l'errore solo se non è un errore ripetuto
                    if not hasattr(self, '_last_connection_error') or self._last_connection_error != str(e):
                        self._safe_show_error("Errore di connessione", "Impossibile connettersi al server. Verifica la connessione e riprova.")
                        self._last_connection_error = str(e)
            except Exception:
                pass
                
        except Exception as e:
            print(f"Errore generico: {type(e).__name__}: {e}")
            games = []
            # Controlla se l'applicazione è ancora attiva prima di mostrare messagebox
            try:
                if self.winfo_exists() and hasattr(self, 'controller') and self.controller.winfo_exists():
                    self._safe_show_error("Errore", f"Si è verificato un errore: {str(e)}")
            except Exception:
                return
                print("✗ Impossibile mostrare dialog di errore: applicazione in chiusura")
     

        # Aggiorna UI solo se necessario
        try:
            self.clear_content()
            
            if not games:
                if hasattr(self, 'content_container') and self.content_container.winfo_exists():
                    ttk.Label(self.content_container, text="Nessuna partita in attesa", style="TLabel").pack(pady=(10, 0))
                return 
            
            for i, game in enumerate(games):
                self.widgets.add_waiting_game_widget(game)  
            
        except Exception as e:
            print(f"Errore durante aggiornamento UI: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def update_received_requests(self):
        """Mostra la lista delle richieste ricevute (SOLO lista locale - NO polling)"""
        self.clear_content()
        received_requests = self.request_manager.get_received_requests()
        if not received_requests:
            ttk.Label(self.content_container, text="Nessuna richiesta ricevuta", style="TLabel").pack(pady=(10, 0))
            return
        
        for request in received_requests:
            self.widgets.add_received_request_widget(request)

    def update_sent_requests(self):
        """Mostra la lista delle richieste effettuate (SOLO lista locale - NO polling)"""
        self.clear_content()
        sent_requests = self.request_manager.get_sent_requests()
        if not sent_requests:
            ttk.Label(self.content_container, text="Nessuna richiesta effettuata", style="TLabel").pack(pady=(10, 0))
            return
        
        for request in sent_requests:
            self.widgets.add_sent_request_widget(request)

    def _safe_show_error(self, title, message):
        """Mostra un messagebox di errore in modo sicuro, evitando errori quando l'app è in chiusura"""
        try:
            # Verifica che l'applicazione sia ancora attiva
            if self.winfo_exists() and hasattr(self, 'controller') and self.controller.winfo_exists():
                # Mostra il messagebox con un timeout automatico usando after()
                self._show_error_with_timeout(title, message)
            else:
                print(f"⚠ App in chiusura - errore non mostrato: {title}: {message}")
        except Exception as e:
            print(f"⚠ Impossibile mostrare errore - app probabilmente in chiusura: {e}")

    def _show_error_with_timeout(self, title, message):
        """Mostra un dialog di errore che si chiude automaticamente dopo 3 secondi"""
        try:
            # Crea una finestra di errore personalizzata
            error_window = tk.Toplevel(self)
            error_window.title(title)
            error_window.geometry("350x150")
            error_window.resizable(False, False)
            error_window.configure(bg="#ffebee")
            
            # Centra la finestra
            error_window.transient(self)
            error_window.grab_set()
            
            # Frame per il contenuto
            frame = tk.Frame(error_window, bg="#ffebee")
            frame.pack(expand=True, fill="both", padx=20, pady=20)
            
            # Icona e messaggio
            icon_label = tk.Label(frame, text="⚠", font=("Arial", 24), bg="#ffebee", fg="#d32f2f")
            icon_label.pack(pady=(0, 10))
            
            msg_label = tk.Label(frame, text=message, wraplength=300, justify="center", 
                               bg="#ffebee", fg="#d32f2f")
            msg_label.pack(pady=(0, 15))
            
            # Bottone OK
            ok_btn = tk.Button(frame, text="OK", command=error_window.destroy, 
                             bg="#d32f2f", fg="white", padx=30)
            ok_btn.pack()
            
            # Auto-chiusura dopo 3 secondi
            def auto_close():
                try:
                    if error_window.winfo_exists():
                        error_window.destroy()
                except Exception:
                    pass
            
            error_window.after(3000, auto_close)
            
        except Exception as e:
            # Fallback: stampa solo l'errore
            print(f"{title}: {message}")
            print(f"Errore creazione dialog: {e}")