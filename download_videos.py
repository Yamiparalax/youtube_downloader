# ===================== IMPORTS =====================
import asyncio
import yt_dlp
import flet as ft
import os
import gc
import warnings

warnings.filterwarnings('ignore')

# ===================== CONFIG =====================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(ROOT_DIR, 'downloads')
VIDEO_FOLDER = os.path.join(DOWNLOAD_DIR, 'Videos')
AUDIO_FOLDER = os.path.join(DOWNLOAD_DIR, 'Audios')

os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# ===================== função configurar_ytdlp_opções =====================
def configurar_ytdlp_opções(formato, pasta_download):
    ydl_opts = {
        "outtmpl": os.path.join(pasta_download, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [],
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

# ===================== função baixar_midia =====================
async def baixar_midia(url, formato, atualizar_progresso, atualizar_status):
    pasta_download = VIDEO_FOLDER if formato == "Video" else AUDIO_FOLDER
    ydl_opts = configurar_ytdlp_opções(formato, pasta_download)

    def hook(d):
        if d['status'] == 'downloading':
            filename = d.get('info_dict', {}).get('title', 'Unknown Title')
            progress = d.get('_percent_str', '0.0%').strip()
            try:
                progress_float = float(progress.replace('%', ''))
                atualizar_progresso(progress_float)
                atualizar_status(f"Downloading: {filename} - {progress}")
            except:
                pass
        elif d['status'] == 'finished':
            atualizar_progresso(100)
            atualizar_status(f"Finished: {d.get('info_dict', {}).get('title', 'Unknown Title')}")

    ydl_opts["progress_hooks"].append(hook)

    gc.disable()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    gc.enable()

# ===================== função atualizar_fila_interface =====================
def atualizar_fila_interface(page, queue, downloads_concluidos, fila_texto, resumo_texto):
    fila_texto.value = "\n".join([item['url'] for item in queue]) or "Nenhum download na fila"
    resumo_texto.value = f"Concluídos: {downloads_concluidos} | Restantes: {len(queue)}"
    if len(queue) == 0 and downloads_concluidos > 0:
        resumo_texto.value = f"✅ Todos os downloads foram concluídos"
    page.update()

# ===================== função atualizar_progresso =====================
def atualizar_progresso(percentual, progresso_bar, page):
    progresso_bar.value = percentual / 100
    page.update()

# ===================== função atualizar_status =====================
def atualizar_status(msg, status_texto, page):
    status_texto.value = f"Status: {msg}"
    page.update()

# ===================== função iniciar_download =====================
async def iniciar_download(queue, atualizar_progresso_cb, atualizar_status_cb, page, downloads_concluidos, fila_texto, resumo_texto, progresso_bar, status_texto):
    while queue:
        item = queue.pop(0)
        atualizar_fila_interface(page, queue, downloads_concluidos, fila_texto, resumo_texto)
        await baixar_midia(item['url'], item['formato'],
                           lambda p: atualizar_progresso_cb(p, progresso_bar, page),
                           lambda m: atualizar_status_cb(m, status_texto, page))
        downloads_concluidos += 1
        atualizar_fila_interface(page, queue, downloads_concluidos, fila_texto, resumo_texto)

    progresso_bar.value = 0
    atualizar_status_cb("Idle", status_texto, page)

# ===================== função main =====================
def main(page: ft.Page):
    page.title = "YouTube Downloader"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.window_width = 500
    page.window_height = 550
    page.theme = ft.Theme(color_scheme_seed="purple", font_family="monospace")
    page.bgcolor = ft.colors.PINK_50

    queue = []
    downloads_concluidos = 0

    progresso_bar = ft.ProgressBar(width=400, height=10)
    fila_texto = ft.Text("Nenhum download na fila", width=400)
    status_texto = ft.Text("Status: Idle", width=400, color=ft.colors.PINK_900, weight=ft.FontWeight.BOLD)
    resumo_texto = ft.Text("Concluídos: 0 | Restantes: 0", width=400, color=ft.colors.PURPLE_900, weight=ft.FontWeight.BOLD)

    # ===================== função adicionar_na_fila =====================
    def adicionar_na_fila(e):
        url = input_url.value.strip()
        if url:
            queue.append({
                "url": url,
                "formato": dropdown_formato.value,
            })
            atualizar_fila_interface(page, queue, downloads_concluidos, fila_texto, resumo_texto)
            input_url.value = ""
            page.update()
            asyncio.run(iniciar_download(queue, atualizar_progresso, atualizar_status, page, downloads_concluidos, fila_texto, resumo_texto, progresso_bar, status_texto))

    input_url = ft.TextField(label="Cole a URL do YouTube", width=400)
    dropdown_formato = ft.Dropdown(
        label="Escolha o formato",
        options=[ft.dropdown.Option("Video"), ft.dropdown.Option("Audio")],
        value="Video",
        width=200
    )
    btn_add_queue = ft.ElevatedButton("Adicionar à Fila + Baixar", on_click=adicionar_na_fila, bgcolor=ft.colors.PURPLE, color=ft.colors.WHITE, style=ft.ButtonStyle(shadow_color=ft.colors.BLACK))

    page.add(
        ft.Text("🎬 YouTube Downloader", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.PINK_900, italic=True, text_align=ft.TextAlign.CENTER),
        input_url,
        dropdown_formato,
        btn_add_queue,
        ft.Text("Progresso do download:", weight=ft.FontWeight.BOLD),
        progresso_bar,
        status_texto,
        resumo_texto,
        ft.Text("Fila:", weight=ft.FontWeight.BOLD),
        fila_texto
    )

# ===================== função executar_app =====================
if __name__ == "__main__":
    ft.app(target=main)
