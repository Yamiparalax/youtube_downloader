# ===================== IMPORTS =====================
import os
import gc
import warnings
import asyncio
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QComboBox, QListWidget, QProgressBar
)
from PySide6.QtCore import Qt, QThreadPool, QRunnable, Slot, Signal, QObject

warnings.filterwarnings('ignore')

# ===================== CONFIG =====================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_FOLDER = os.path.join(ROOT_DIR, 'Videos')
AUDIO_FOLDER = os.path.join(ROOT_DIR, 'Audios')

os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# ===================== função configurar_ytdlp_opções =====================
def configurar_ytdlp_opções(formato, pasta_download, hook):
    ydl_opts = {
        "outtmpl": os.path.join(pasta_download, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [hook],
        "overwrites": True,
        "concurrent_fragment_downloads": 4,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True
    }

    if formato == "Video":
        ydl_opts.update({
            "format": "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best[height<=1440]",
        })
    else:  # Audio
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })

    return ydl_opts

# ===================== classe WorkerSignals =====================
class WorkerSignals(QObject):
    progresso = Signal(float, str)
    concluido = Signal(str)
    erro = Signal(str)

# ===================== classe DownloadWorker =====================
class DownloadWorker(QRunnable):
    def __init__(self, url, formato, pasta_download):
        super().__init__()
        self.url = url
        self.formato = formato
        self.pasta_download = pasta_download
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        def hook(d):
            if d['status'] == 'downloading':
                filename = d.get('info_dict', {}).get('title', 'Unknown Title')
                progress = d.get('_percent_str', '0.0%').strip()
                try:
                    progress_float = float(progress.replace('%', ''))
                    self.signals.progresso.emit(progress_float, filename)
                except:
                    pass
            elif d['status'] == 'finished':
                filename = d.get('info_dict', {}).get('title', 'Unknown Title')
                self.signals.concluido.emit(filename)

        ydl_opts = configurar_ytdlp_opções(self.formato, self.pasta_download, hook)

        gc.disable()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            self.signals.erro.emit(str(e))
            for f in os.listdir(self.pasta_download):
                if f.endswith(".part") or f.endswith(".tmp"):
                    try:
                        os.remove(os.path.join(self.pasta_download, f))
                    except:
                        pass
        gc.enable()

# ===================== função main =====================
class YouTubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader — C6 Version")
        self.setGeometry(300, 200, 600, 500)
        self.threadpool = QThreadPool()

        # Estado
        self.queue = []
        self.downloads_em_andamento = {}
        self.downloads_concluidos = []

        # Layout principal
        layout = QVBoxLayout()

        titulo = QLabel("🎬 YouTube Downloader")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 22px; font-weight: bold; color: purple;")

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Cole a URL do YouTube")

        self.dropdown_formato = QComboBox()
        self.dropdown_formato.addItems(["Video", "Audio"])

        self.btn_add_queue = QPushButton("Adicionar à Fila + Baixar")
        self.btn_add_queue.clicked.connect(self.adicionar_na_fila)

        hbox = QHBoxLayout()
        hbox.addWidget(self.input_url)
        hbox.addWidget(self.dropdown_formato)
        hbox.addWidget(self.btn_add_queue)

        # Labels
        self.label_status = QLabel("Status: Aguardando...")
        self.label_resumo = QLabel("Concluídos: 0 | Em andamento: 0 | Na fila: 0")

        # Barras e listas
        self.progresso_bar = QProgressBar()
        self.progresso_bar.setValue(0)

        self.lista_fila = QListWidget()
        self.lista_andamento = QListWidget()
        self.lista_concluidos = QListWidget()

        # Layout final
        layout.addWidget(titulo)
        layout.addLayout(hbox)
        layout.addWidget(QLabel("Progresso atual:"))
        layout.addWidget(self.progresso_bar)
        layout.addWidget(self.label_status)
        layout.addWidget(self.label_resumo)

        layout.addWidget(QLabel("📋 Fila de downloads:"))
        layout.addWidget(self.lista_fila)
        layout.addWidget(QLabel("⏳ Em andamento:"))
        layout.addWidget(self.lista_andamento)
        layout.addWidget(QLabel("✅ Concluídos:"))
        layout.addWidget(self.lista_concluidos)

        self.setLayout(layout)

# ===================== função atualizar_interface =====================
    def atualizar_interface(self):
        self.lista_fila.clear()
        for item in self.queue:
            self.lista_fila.addItem(f"{item['url']} [{item['formato']}]")

        self.lista_andamento.clear()
        for titulo in self.downloads_em_andamento.values():
            self.lista_andamento.addItem(titulo)

        self.lista_concluidos.clear()
        for titulo in self.downloads_concluidos:
            self.lista_concluidos.addItem(titulo)

        self.label_resumo.setText(f"Concluídos: {len(self.downloads_concluidos)} | Em andamento: {len(self.downloads_em_andamento)} | Na fila: {len(self.queue)}")

# ===================== função adicionar_na_fila =====================
    def adicionar_na_fila(self):
        url = self.input_url.text().strip()
        formato = self.dropdown_formato.currentText()
        if url:
            self.queue.append({"url": url, "formato": formato})
            self.input_url.clear()
            self.iniciar_proximo_download()

# ===================== função iniciar_proximo_download =====================
    def iniciar_proximo_download(self):
        if not self.queue or len(self.downloads_em_andamento) > 0:
            self.atualizar_interface()
            return

        item = self.queue.pop(0)
        pasta_download = VIDEO_FOLDER if item['formato'] == "Video" else AUDIO_FOLDER

        worker = DownloadWorker(item['url'], item['formato'], pasta_download)
        worker.signals.progresso.connect(self.atualizar_progresso)
        worker.signals.concluido.connect(self.finalizar_download)
        worker.signals.erro.connect(self.tratar_erro)

        self.downloads_em_andamento[item['url']] = "Iniciando..."
        self.threadpool.start(worker)
        self.atualizar_interface()

# ===================== função atualizar_progresso =====================
    def atualizar_progresso(self, percentual, titulo):
        self.progresso_bar.setValue(int(percentual))
        self.label_status.setText(f"Baixando: {titulo} - {percentual:.1f}%")
        self.downloads_em_andamento = {k: titulo for k in self.downloads_em_andamento.keys()}
        self.atualizar_interface()

# ===================== função finalizar_download =====================
    def finalizar_download(self, titulo):
        self.progresso_bar.setValue(0)
        self.label_status.setText(f"Concluído: {titulo}")
        self.downloads_concluidos.append(titulo)
        self.downloads_em_andamento.clear()
        self.iniciar_proximo_download()

# ===================== função tratar_erro =====================
    def tratar_erro(self, erro_msg):
        self.label_status.setText(f"[❌ ERRO] {erro_msg}")
        self.downloads_em_andamento.clear()
        self.iniciar_proximo_download()

# ===================== função executar_app =====================
if __name__ == "__main__":
    app = QApplication([])
    janela = YouTubeDownloader()
    janela.show()
    app.exec()
