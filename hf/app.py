import gradio as gr
import os
import fitz
import base64
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKS_DIR = os.path.join(BASE_DIR, "books")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

opened_docs = {}

CSS = """
.hidden-control-room { position: absolute !important; visibility: hidden !important; pointer-events: none; }

.shelf-container {
    background: linear-gradient(to bottom, #5d4037 0%, #4e342e 100%);
    padding: 60px 40px; border-radius: 4px; border-bottom: 45px solid #3e2723; 
    box-shadow: inset 0 10px 30px rgba(0,0,0,0.5), 0 20px 40px rgba(0,0,0,0.4), 0 5px 0 #2d1d1a;
    display: flex; 
    flex-direction: row; 
    flex-wrap: nowrap; 
    justify-content: flex-start; 
    gap: 25px; 
    width: 100%;
    max-width: 1080px; 
    margin: 40px auto; 
    min-height: 400px;
    box-sizing: border-box; 
    position: relative;
    overflow-x: auto; 
    scrollbar-width: thin; 
    scrollbar-color: #8d6e63 transparent;
}

.shelf-container::-webkit-scrollbar { height: 8px; }
.shelf-container::-webkit-scrollbar-thumb { background: #8d6e63; border-radius: 10px; }
.shelf-container::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }

.book-card { 
    cursor: pointer; 
    transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1); 
    text-align: center; 
    flex: 0 0 180px; 
    position: relative; 
    z-index: 2; 
}
.book-card:hover { transform: translateY(-25px) rotate(-2deg) scale(1.1); z-index: 10; }
.book-cover { width: 100%; height: 260px; object-fit: cover; border-radius: 2px 5px 5px 2px; border-left: 12px solid rgba(0,0,0,0.1); box-shadow: 5px 5px 15px rgba(0,0,0,0.5); background: #333; }

#reader_col { background: #e8e4e1 !important; transition: all 0.3s; padding: 20px; }

#reader_col:fullscreen #back_btn_id { display: none !important; }
#reader_col:-webkit-full-screen #back_btn_id { display: none !important; }

#reader_col:fullscreen { 
    width: 100vw !important; 
    height: 100vh !important; 
    background: #000 !important; 
    display: flex !important; 
    flex-direction: column !important;
    padding: 0 !important;
    justify-content: center !important;
}

.reader-container { 
    position: relative !important; background: transparent !important; 
    display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center;
    width: 100%; height: 100%; overflow: hidden;
}

.nav-overlay-btn { 
    position: absolute !important; top: 50% !important; transform: translateY(-50%) !important; 
    z-index: 1000 !important; background: rgba(255, 255, 255, 0.2) !important; 
    border: none !important; border-radius: 50% !important; 
    width: 80px !important; height: 80px !important; font-size: 40px !important; 
    color: white !important; cursor: pointer;
}
.nav-overlay-btn:hover { background: rgba(255, 255, 255, 0.5) !important; }
.prev-pos { left: 20px !important; }
.next-pos { right: 20px !important; }

.page-overlay-label { 
    position: absolute !important; bottom: 20px !important; left: 50% !important; 
    transform: translateX(-50%) !important; background: rgba(0, 0, 0, 0.7) !important; 
    color: white !important; padding: 5px 15px !important; border-radius: 20px !important; z-index: 1001;
}

.page-img-render { max-height: 98vh; max-width: 98vw; width: auto; height: auto; object-fit: contain; }
"""

JS_LOGIC = """
function() {
    const updateFSButtonText = () => {
        const btn = document.querySelector('#fs_btn_id');
        if (!btn) return;
        btn.innerText = document.fullscreenElement ? "❌ THOÁT" : "📺 TOÀN MÀN HÌNH";
    };

    window.toggleFS = () => {
        const container = document.getElementById('reader_col');
        if (!document.fullscreenElement) {
            container.requestFullscreen().catch(err => alert("Lỗi: " + err.message));
        } else {
            document.exitFullscreen();
        }
    };

    window.triggerBookOpen = (name) => {
        const input = document.querySelector('#hidden_input textarea');
        if(input) {
            input.value = name;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            setTimeout(() => document.getElementById('hidden_btn').click(), 50);
        }
    };

    if (!window.kbSubscribed) {
        document.addEventListener('fullscreenchange', updateFSButtonText);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') document.querySelector('.prev-pos')?.click();
            if (e.key === 'ArrowRight') document.querySelector('.next-pos')?.click();
        });
        window.kbSubscribed = true;
    }
}
"""

@lru_cache(maxsize=128)
def get_page_render(pdf_name, page_num):
    try:
        pdf_path = os.path.join(BOOKS_DIR, f"{pdf_name}.pdf")
        if pdf_name not in opened_docs:
            opened_docs[pdf_name] = fitz.open(pdf_path)
        doc = opened_docs[pdf_name]
        p_idx = max(0, min(page_num, len(doc) - 1))
        page = doc.load_page(p_idx)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
        return f'<img src="data:image/png;base64,{img_b64}" class="page-img-render">', len(doc), p_idx
    except:
        return "<h3>LỖI TẢI TRANG</h3>", 0, 0

def generate_shelf():
    if not os.path.exists(BOOKS_DIR): return "<h3>KHÔNG TÌM THẤY BOOKS</h3>"
    files = sorted([f for f in os.listdir(BOOKS_DIR) if f.lower().endswith('.pdf')])
    html = '<div class="shelf-container">'
    for f in files:
        stem = os.path.splitext(f)[0]
        cover_src = "https://via.placeholder.com/180x260"
        for ext in ['.png', '.jpg', '.jpeg']:
            cp = os.path.join(IMAGES_DIR, stem + ext)
            if os.path.exists(cp):
                with open(cp, "rb") as i:
                    cover_src = f"data:image/png;base64,{base64.b64encode(i.read()).decode()}"
                break
        html += f'<div class="book-card" onclick="triggerBookOpen(\'{stem}\')"><img class="book-cover" src="{cover_src}"></div>'
    return html + '</div>'

with gr.Blocks(css=CSS) as demo:
    current_book = gr.State("")
    current_page = gr.State(0)

    with gr.Row(elem_classes="hidden-control-room"):
        gr_input = gr.Textbox(elem_id="hidden_input")
        gr_btn = gr.Button("Action", elem_id="hidden_btn")

    with gr.Column() as shelf_view:
        gr.Markdown("<h1 style='text-align:center'>📚 digital-library</h1>")
        gr.HTML(generate_shelf())

    with gr.Column(visible=False, elem_id="reader_col") as reader_view:
        with gr.Row():
            back_btn = gr.Button("⬅ QUAY LẠI", variant="secondary", elem_id="back_btn_id")
            fs_btn = gr.Button("📺 TOÀN MÀN HÌNH", variant="primary", elem_id="fs_btn_id")
            fs_btn.click(None, None, None, js="() => { window.toggleFS(); }")
            
        with gr.Group(elem_classes="reader-container"):
            prev_btn = gr.Button("❮", elem_classes="nav-overlay-btn prev-pos")
            next_btn = gr.Button("❯", elem_classes="nav-overlay-btn next-pos")
            page_info = gr.HTML()
            pdf_display = gr.HTML()

    def select_book(name):
        yield {shelf_view: gr.update(visible=False), reader_view: gr.update(visible=True), pdf_display: "<h3>Đang tải...</h3>"}
        html, total, p_idx = get_page_render(name, 0)
        yield {current_book: name, current_page: p_idx, pdf_display: html, page_info: f'<div class="page-overlay-label">1 / {total}</div>'}

    def move_page(name, p_num, delta):
        if not name: return p_num, "", ""
        html, total, new_idx = get_page_render(name, p_num + delta)
        return new_idx, html, f'<div class="page-overlay-label">{new_idx + 1} / {total}</div>'

    gr_btn.click(select_book, [gr_input], [current_book, current_page, pdf_display, page_info, shelf_view, reader_view])
    prev_btn.click(move_page, [current_book, current_page, gr.State(-1)], [current_page, pdf_display, page_info])
    next_btn.click(move_page, [current_book, current_page, gr.State(1)], [current_page, pdf_display, page_info])
    back_btn.click(lambda: (gr.update(visible=True), gr.update(visible=False)), None, [shelf_view, reader_view])

    demo.load(None, None, None, js=JS_LOGIC)

if __name__ == "__main__":
    demo.launch()