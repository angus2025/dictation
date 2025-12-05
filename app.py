# app.py  —— 終極零延遲版（2025年最新兼容）
from flask import Flask, request, send_file
from flask_cors import CORS
import edge_tts
import asyncio
import io
import threading
import tempfile
import os
import csv

app = Flask(__name__)
CORS(app)

# ==================== 讀取 words.csv ====================
def load_word_pairs():
    pairs = []
    try:
        with open("words.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eng = row["english"].strip().lower()
                chi = row["chinese"].strip()
                if eng:
                    pairs.append({"en": eng, "zh": chi})
        print(f"成功載入 {len(pairs)} 個英中單字")
    except FileNotFoundError:
        print("找不到 words.csv，使用內建單字")
        pairs = [{"en": "cat", "zh": "小貓"}, {"en": "dog", "zh": "小狗"}]
    return pairs

WORD_PAIRS = load_word_pairs()


# 全域快取：同一個單字永遠只合成一次
cache = {}
cache_lock = threading.Lock()

@app.route("/")
def index():
    with open("dictation.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # 把 JS 裡的單字陣列整個換掉
    js_array = "const wordPairs = " + str(WORD_PAIRS) + ";"
    html = html.replace(
        'const wordPairs = [];  // PLACEHOLDER',
        js_array
    )
    return html, 200, {'Content-Type': 'text/html'}

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/speak", methods=["POST"])
def speak():
    text = request.json["text"].strip().lower()
    
    # 快取命中 → 瞬間回傳（<50ms）
    with cache_lock:
        if text in cache:
            return send_file(
                io.BytesIO(cache[text]),
                mimetype="audio/mp3",
                download_name="speech.mp3"
            )
    
    # 沒快取才合成（只發生一次）
    async def tts_task():
        communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural")
        # 建立臨時檔案（edge-tts 只接受路徑）
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        try:
            await communicate.save(tmp.name)
            with open(tmp.name, "rb") as f:
                mp3_data = f.read()
            return mp3_data
        finally:
            os.unlink(tmp.name)  # 一定刪掉臨時檔

    # 同步執行 async
    mp3_bytes = asyncio.run(tts_task())
    
    # 存進快取
    with cache_lock:
        cache[text] = mp3_bytes
    
    return send_file(
        io.BytesIO(mp3_bytes),
        mimetype="audio/mp3",
        download_name="speech.mp3"
    )

#if __name__ == "__main__":
#    print("極速超自然聽寫遊戲已啟動！")
#    print("→ 請用瀏覽器打開： http://localhost:5000")
#    app.run(port=5000, threaded=True)
    
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
