# ============================================================
# US SYARIAH STOCK - TELEGRAM BOT HANDLER
# Fitur: /portfolio_us, /beli_us, /jual_us, /entry_us,
#        /screener_us, /watchlist_us
# Data disimpan di file JSON lokal (portfolio_us.json, watchlist_us.json)
# 🤖 Powered by Clau - Kandip's smartest assistant 😎
# ============================================================

import os
import json
import time
import logging
import requests
import yfinance as yf
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

PORTFOLIO_FILE = "portfolio_us.json"
WATCHLIST_FILE = "watchlist_us.json"

# ============================================================
# HELPERS: SIMPAN & LOAD DATA
# ============================================================
def load_json(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def save_json(filepath: str, data: dict):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

# ============================================================
# HELPERS: TELEGRAM
# ============================================================
def kirim(chat_id: str, pesan: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": pesan,
        "parse_mode": "HTML"
    }, timeout=30)

def get_harga(ticker: str) -> float:
    try:
        info = yf.Ticker(ticker).info
        return float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    except:
        return 0.0

def get_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

# ============================================================
# /beli_us TICKER JUMLAH HARGA
# Contoh: /beli_us AAPL 10 185.50
# ============================================================
def cmd_beli(chat_id: str, args: list):
    if len(args) < 3:
        kirim(chat_id,
            "❌ Format salah!\n\n"
            "Gunakan: <code>/beli_us TICKER JUMLAH HARGA</code>\n"
            "Contoh: <code>/beli_us AAPL 10 185.50</code>"
        )
        return

    ticker = args[0].upper()
    try:
        jumlah = float(args[1])
        harga  = float(args[2])
    except:
        kirim(chat_id, "❌ Jumlah dan harga harus berupa angka.")
        return

    portfolio = load_json(PORTFOLIO_FILE)

    if ticker not in portfolio:
        portfolio[ticker] = {"lots": []}

    portfolio[ticker]["lots"].append({
        "jumlah": jumlah,
        "harga_beli": harga,
        "tanggal": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

    save_json(PORTFOLIO_FILE, portfolio)

    total_nilai = jumlah * harga
    kirim(chat_id,
        f"✅ <b>Pembelian dicatat!</b>\n\n"
        f"📌 Ticker : <b>{ticker}</b>\n"
        f"📦 Jumlah : {jumlah:.0f} shares\n"
        f"💵 Harga  : ${harga:.2f}\n"
        f"💰 Total  : ${total_nilai:,.2f}\n\n"
        f"🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"
    )

# ============================================================
# /jual_us TICKER JUMLAH HARGA
# Contoh: /jual_us AAPL 5 200.00
# ============================================================
def cmd_jual(chat_id: str, args: list):
    if len(args) < 3:
        kirim(chat_id,
            "❌ Format salah!\n\n"
            "Gunakan: <code>/jual_us TICKER JUMLAH HARGA</code>\n"
            "Contoh: <code>/jual_us AAPL 5 200.00</code>"
        )
        return

    ticker = args[0].upper()
    try:
        jumlah_jual = float(args[1])
        harga_jual  = float(args[2])
    except:
        kirim(chat_id, "❌ Jumlah dan harga harus berupa angka.")
        return

    portfolio = load_json(PORTFOLIO_FILE)

    if ticker not in portfolio or not portfolio[ticker]["lots"]:
        kirim(chat_id, f"❌ <b>{ticker}</b> tidak ada di portfolio kamu.")
        return

    # Hitung rata-rata harga beli
    lots = portfolio[ticker]["lots"]
    total_shares = sum(l["jumlah"] for l in lots)
    total_cost   = sum(l["jumlah"] * l["harga_beli"] for l in lots)
    avg_beli     = total_cost / total_shares if total_shares > 0 else 0

    if jumlah_jual > total_shares:
        kirim(chat_id, f"❌ Jumlah jual ({jumlah_jual}) melebihi kepemilikan ({total_shares:.0f} shares).")
        return

    # Hitung profit/loss
    profit = (harga_jual - avg_beli) * jumlah_jual
    pct    = ((harga_jual - avg_beli) / avg_beli * 100) if avg_beli > 0 else 0
    emoji  = "🟢" if profit >= 0 else "🔴"

    # Kurangi dari portfolio (FIFO)
    sisa_jual = jumlah_jual
    lots_baru = []
    for lot in lots:
        if sisa_jual <= 0:
            lots_baru.append(lot)
        elif lot["jumlah"] <= sisa_jual:
            sisa_jual -= lot["jumlah"]
        else:
            lot["jumlah"] -= sisa_jual
            sisa_jual = 0
            lots_baru.append(lot)

    if lots_baru:
        portfolio[ticker]["lots"] = lots_baru
    else:
        del portfolio[ticker]

    save_json(PORTFOLIO_FILE, portfolio)

    kirim(chat_id,
        f"{emoji} <b>Penjualan dicatat!</b>\n\n"
        f"📌 Ticker     : <b>{ticker}</b>\n"
        f"📦 Dijual     : {jumlah_jual:.0f} shares\n"
        f"💵 Harga Jual : ${harga_jual:.2f}\n"
        f"📊 Avg Beli   : ${avg_beli:.2f}\n"
        f"{'🟢 Profit' if profit >= 0 else '🔴 Loss'}    : ${abs(profit):,.2f} ({pct:+.2f}%)\n\n"
        f"🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"
    )

# ============================================================
# /portfolio_us
# ============================================================
def cmd_portfolio(chat_id: str):
    portfolio = load_json(PORTFOLIO_FILE)

    if not portfolio:
        kirim(chat_id,
            "📂 Portfolio US kamu masih kosong.\n\n"
            "Tambahkan dengan: <code>/beli_us TICKER JUMLAH HARGA</code>\n"
            "Contoh: <code>/beli_us AAPL 10 185.50</code>"
        )
        return

    kirim(chat_id, "⏳ Mengambil data harga terkini... harap tunggu.")

    total_modal  = 0.0
    total_nilai  = 0.0
    baris_list   = []

    for ticker, data in portfolio.items():
        lots = data.get("lots", [])
        if not lots:
            continue

        total_shares = sum(l["jumlah"] for l in lots)
        total_cost   = sum(l["jumlah"] * l["harga_beli"] for l in lots)
        avg_beli     = total_cost / total_shares

        harga_kini = get_harga(ticker)
        if harga_kini == 0:
            harga_kini = avg_beli  # fallback

        nilai_kini = total_shares * harga_kini
        pl         = nilai_kini - total_cost
        pct        = (pl / total_cost * 100) if total_cost > 0 else 0
        emoji      = "🟢" if pl >= 0 else "🔴"

        total_modal += total_cost
        total_nilai += nilai_kini

        baris_list.append(
            f"{emoji} <b>{ticker}</b>\n"
            f"   {total_shares:.0f} shares | Avg: ${avg_beli:.2f} | Kini: ${harga_kini:.2f}\n"
            f"   Nilai: ${nilai_kini:,.2f} | P/L: ${pl:+,.2f} ({pct:+.2f}%)\n"
        )

    total_pl  = total_nilai - total_modal
    total_pct = (total_pl / total_modal * 100) if total_modal > 0 else 0
    emoji_tot = "🟢" if total_pl >= 0 else "🔴"

    pesan  = "🇺🇸 <b>PORTFOLIO US SYARIAH</b>\n"
    pesan += f"📅 {datetime.now().strftime('%d %b %Y %H:%M')}\n"
    pesan += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    pesan += "\n".join(baris_list)
    pesan += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    pesan += f"💼 Modal Total : ${total_modal:,.2f}\n"
    pesan += f"📈 Nilai Kini  : ${total_nilai:,.2f}\n"
    pesan += f"{emoji_tot} Total P/L   : ${total_pl:+,.2f} ({total_pct:+.2f}%)\n\n"
    pesan += "🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"

    kirim(chat_id, pesan)

# ============================================================
# /entry_us TICKER
# Contoh: /entry_us AAPL
# ============================================================
def cmd_entry(chat_id: str, args: list):
    if not args:
        kirim(chat_id,
            "❌ Format salah!\n\n"
            "Gunakan: <code>/entry_us TICKER</code>\n"
            "Contoh: <code>/entry_us AAPL</code>"
        )
        return

    ticker = args[0].upper()
    kirim(chat_id, f"⏳ Menganalisis <b>{ticker}</b>... harap tunggu.")

    try:
        import pandas as pd
        df   = yf.download(ticker, period="3mo", interval="1d", progress=False)
        info = get_info(ticker)

        if df.empty:
            kirim(chat_id, f"❌ Data untuk {ticker} tidak ditemukan.")
            return

        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        harga  = float(close.iloc[-1])
        nama   = info.get("shortName", ticker)

        # Support & Resistance (20 hari terakhir)
        support    = float(low.rolling(20).min().iloc[-1])
        resistance = float(high.rolling(20).max().iloc[-1])

        # Stop Loss = 2% di bawah support
        stop_loss = support * 0.98

        # Target 1 = resistance, Target 2 = resistance + (resistance - support)
        target1 = resistance
        target2 = resistance + (resistance - support) * 0.5

        # Risk/Reward
        risk    = harga - stop_loss
        reward1 = target1 - harga
        rr1     = reward1 / risk if risk > 0 else 0

        # RSI
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss
        rsi   = float((100 - (100 / (1 + rs))).iloc[-1])

        # Rekomendasi posisi
        if harga < support * 1.02:
            zona = "🟢 Zona BUY - Harga dekat support"
        elif harga > resistance * 0.98:
            zona = "🔴 Zona MAHAL - Harga dekat resistance"
        else:
            zona = "🟡 Zona TENGAH - Tunggu konfirmasi"

        pesan = (
            f"📊 <b>ENTRY CALCULATOR US</b>\n"
            f"📌 {nama} (<b>{ticker}</b>)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Harga Kini   : ${harga:.2f}\n"
            f"📉 Support      : ${support:.2f}\n"
            f"📈 Resistance   : ${resistance:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 Stop Loss    : ${stop_loss:.2f}\n"
            f"🎯 Target 1     : ${target1:.2f}\n"
            f"🎯 Target 2     : ${target2:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️  Risk/Reward  : 1 : {rr1:.1f}\n"
            f"📊 RSI          : {rsi:.1f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{zona}\n\n"
            f"⚠️ <i>Bukan saran investasi. DYOR!</i>\n"
            f"🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"
        )
        kirim(chat_id, pesan)

    except Exception as e:
        kirim(chat_id, f"❌ Error saat analisis {ticker}: {e}")

# ============================================================
# /watchlist_us [TICKER] atau /watchlist_us hapus TICKER
# ============================================================
def cmd_watchlist(chat_id: str, args: list):
    watchlist = load_json(WATCHLIST_FILE)
    tickers   = watchlist.get("tickers", [])

    # Tampilkan watchlist
    if not args:
        if not tickers:
            kirim(chat_id,
                "👁 Watchlist US kamu masih kosong.\n\n"
                "Tambah: <code>/watchlist_us AAPL</code>\n"
                "Hapus : <code>/watchlist_us hapus AAPL</code>"
            )
            return

        kirim(chat_id, "⏳ Mengambil data watchlist... harap tunggu.")
        pesan = "👁 <b>WATCHLIST US SYARIAH</b>\n"
        pesan += f"📅 {datetime.now().strftime('%d %b %Y %H:%M')}\n"
        pesan += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for tkr in tickers:
            try:
                info  = get_info(tkr)
                harga = get_harga(tkr)
                chg   = info.get("regularMarketChangePercent", 0) or 0
                nama  = info.get("shortName", tkr)[:20]
                emoji = "🟢" if chg >= 0 else "🔴"
                pesan += f"{emoji} <b>{tkr}</b> {nama}\n"
                pesan += f"   ${harga:.2f} | {chg:+.2f}%\n\n"
            except:
                pesan += f"• <b>{tkr}</b> - data tidak tersedia\n\n"

        pesan += "🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"
        kirim(chat_id, pesan)
        return

    # Hapus dari watchlist
    if args[0].lower() == "hapus" and len(args) >= 2:
        ticker = args[1].upper()
        if ticker in tickers:
            tickers.remove(ticker)
            watchlist["tickers"] = tickers
            save_json(WATCHLIST_FILE, watchlist)
            kirim(chat_id, f"✅ <b>{ticker}</b> dihapus dari watchlist.")
        else:
            kirim(chat_id, f"❌ <b>{ticker}</b> tidak ada di watchlist.")
        return

    # Tambah ke watchlist
    ticker = args[0].upper()
    if ticker in tickers:
        kirim(chat_id, f"ℹ️ <b>{ticker}</b> sudah ada di watchlist.")
        return

    if len(tickers) >= 20:
        kirim(chat_id, "❌ Watchlist sudah penuh (maksimal 20 saham).")
        return

    tickers.append(ticker)
    watchlist["tickers"] = tickers
    save_json(WATCHLIST_FILE, watchlist)
    kirim(chat_id, f"✅ <b>{ticker}</b> ditambahkan ke watchlist!\n\nKetik /watchlist_us untuk lihat semua.")

# ============================================================
# /screener_us - Trigger manual screening
# ============================================================
def cmd_screener(chat_id: str):
    kirim(chat_id,
        "⏳ <b>Menjalankan US Syariah Screener...</b>\n\n"
        "Proses ini memakan waktu 3-5 menit.\n"
        "Hasil akan dikirim ke sini setelah selesai."
    )
    try:
        import us_syariah_screener as screener
        screener.main()
    except Exception as e:
        kirim(chat_id, f"❌ Error saat menjalankan screener: {e}")

# ============================================================
# /help_us
# ============================================================
def cmd_help(chat_id: str):
    kirim(chat_id,
        "🇺🇸 <b>US SYARIAH BOT - DAFTAR PERINTAH</b>\n\n"
        "📊 <b>SCREENING</b>\n"
        "/screener_us - Jalankan screening saham US syariah\n\n"
        "💼 <b>PORTFOLIO</b>\n"
        "/portfolio_us - Lihat portfolio kamu\n"
        "/beli_us TICKER JUMLAH HARGA\n"
        "  Contoh: <code>/beli_us AAPL 10 185.50</code>\n"
        "/jual_us TICKER JUMLAH HARGA\n"
        "  Contoh: <code>/jual_us AAPL 5 200.00</code>\n\n"
        "📈 <b>ANALISIS</b>\n"
        "/entry_us TICKER - Kalkulator entry/exit\n"
        "  Contoh: <code>/entry_us NVDA</code>\n\n"
        "👁 <b>WATCHLIST</b>\n"
        "/watchlist_us - Lihat watchlist\n"
        "/watchlist_us TICKER - Tambah saham\n"
        "/watchlist_us hapus TICKER - Hapus saham\n\n"
        "🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"
    )

# ============================================================
# POLLING - Baca perintah dari Telegram
# ============================================================
def polling():
    logger.info("US Syariah Bot mulai polling...")
    offset = None

    while True:
        try:
            url    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            resp   = requests.get(url, params=params, timeout=35)
            data   = resp.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg    = update.get("message", {})
                text   = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if not text or not chat_id:
                    continue

                # Hanya terima dari chat ID yang sudah diset
                if chat_id != TELEGRAM_CHAT_ID:
                    continue

                parts   = text.strip().split()
                command = parts[0].lower().split("@")[0]
                args    = parts[1:] if len(parts) > 1 else []

                logger.info(f"Command diterima: {command} {args}")

                if command == "/beli_us":
                    cmd_beli(chat_id, args)
                elif command == "/jual_us":
                    cmd_jual(chat_id, args)
                elif command == "/portfolio_us":
                    cmd_portfolio(chat_id)
                elif command == "/entry_us":
                    cmd_entry(chat_id, args)
                elif command == "/watchlist_us":
                    cmd_watchlist(chat_id, args)
                elif command == "/screener_us":
                    cmd_screener(chat_id)
                elif command in ("/help_us", "/start"):
                    cmd_help(chat_id)

        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    polling()
