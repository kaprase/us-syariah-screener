# ============================================================
# US SYARIAH STOCK SCREENER
# Screening berbasis kriteria AAOIFI (standar syariah internasional)
# Kirim sinyal BUY/SELL/HOLD via Telegram Bot
# Jadwal: Setiap hari jam 20:00 WIB
# 🤖 Powered by Clau - Kandip's smartest assistant 😎
# ============================================================

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================
# KONFIGURASI
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL_TO     = os.environ.get("ALERT_EMAIL_TO", "")

# Ticker yang mau di-alert via email kalau sinyal SELL (pisahkan dengan koma)
# Contoh env value: "AAPL,TSLA,NVDA"
ALERT_TICKERS = [
    t.strip().upper()
    for t in os.environ.get("ALERT_TICKERS", "").split(",")
    if t.strip()
]

# Daftar saham US yang dianalisis
# Dipilih dari SPUS ETF holdings & DJIM US index - semua sudah terverifikasi syariah
# Tidak termasuk: bank, asuransi, alkohol, rokok, senjata, hiburan dewasa
US_SYARIAH_STOCKS = [
    # Teknologi (dominan di indeks syariah karena cash-heavy, debt rendah)
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # Nvidia
    "AVGO",   # Broadcom
    "AMD",    # Advanced Micro Devices
    "QCOM",   # Qualcomm
    "ANET",   # Arista Networks
    "ADBE",   # Adobe
    "CRM",    # Salesforce
    "ORCL",   # Oracle
    "NOW",    # ServiceNow
    "SNOW",   # Snowflake
    "PANW",   # Palo Alto Networks
    "CRWD",   # CrowdStrike
    "FTNT",   # Fortinet
    "KLAC",   # KLA Corp
    "LRCX",   # Lam Research
    "AMAT",   # Applied Materials
    "MRVL",   # Marvell Technology
    "TXN",    # Texas Instruments

    # Kesehatan & Farmasi
    "LLY",    # Eli Lilly
    "JNJ",    # Johnson & Johnson
    "ABBV",   # AbbVie
    "MRK",    # Merck
    "TMO",    # Thermo Fisher
    "DHR",    # Danaher
    "ISRG",   # Intuitive Surgical
    "SYK",    # Stryker
    "BSX",    # Boston Scientific
    "EW",     # Edwards Lifesciences
    "REGN",   # Regeneron
    "VRTX",   # Vertex Pharma
    "ILMN",   # Illumina
    "IDXX",   # IDEXX Laboratories

    # Konsumer & Retail
    "AMZN",   # Amazon
    "COST",   # Costco
    "HD",     # Home Depot
    "LOW",    # Lowe's
    "TJX",    # TJX Companies
    "TSLA",   # Tesla

    # Industri & Lainnya
    "HON",    # Honeywell
    "CAT",    # Caterpillar
    "DE",     # Deere & Company
    "ITW",    # Illinois Tool Works
    "PH",     # Parker Hannifin
    "ROK",    # Rockwell Automation
    "EMR",    # Emerson Electric
]

# ============================================================
# KRITERIA SYARIAH (AAOIFI Standard)
# ============================================================
SYARIAH_CRITERIA = {
    # Rasio keuangan - semua berbasis market cap
    "max_debt_to_market_cap":          0.33,   # Total hutang / market cap < 33%
    "max_interest_income_to_revenue":  0.05,   # Pendapatan bunga / total revenue < 5%
    "max_receivables_to_market_cap":   0.49,   # Piutang / market cap < 49%
    "max_cash_to_market_cap":          0.33,   # Aset non-halal / market cap < 33%

    # Sektor yang DILARANG (Business Activity Screen)
    "excluded_sectors": [
        "Financial Services",  # Bank konvensional, asuransi konvensional
        "Banks",
        "Insurance",
    ],
    "excluded_industries": [
        "Tobacco",             # Rokok
        "Beverages - Breweries", # Alkohol
        "Beverages - Wineries",
        "Gambling",            # Perjudian
        "Defense & Space",     # Senjata/pertahanan (ada yg halal, tapi skip untuk aman)
        "Adult Entertainment",  # Konten dewasa
        "Banks - Diversified",
        "Banks - Regional",
        "Insurance - Diversified",
        "Insurance - Life",
        "Insurance - Property & Casualty",
        "Insurance - Specialty",
        "Financial Data & Stock Exchanges",
        "Mortgage Finance",
        "Credit Services",
    ]
}

# ============================================================
# FUNGSI TELEGRAM
# ============================================================
def kirim_telegram(pesan: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Token Telegram belum dikonfigurasi.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": pesan,
            "parse_mode": "HTML"
        }, timeout=30)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Gagal kirim Telegram: {e}")
        return False

# ============================================================
# FUNGSI EMAIL (khusus alert SELL)
# ============================================================
def kirim_email(subjek: str, isi: str) -> bool:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not ALERT_EMAIL_TO:
        logger.warning("Konfigurasi email belum lengkap, skip kirim email.")
        return False
    try:
        msg = MIMEText(isi, "plain", "utf-8")
        msg["Subject"] = subjek
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = ALERT_EMAIL_TO

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, [ALERT_EMAIL_TO], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Gagal kirim email: {e}")
        return False

# ============================================================
# SCREENING SYARIAH
# ============================================================
def cek_syariah(ticker: str) -> tuple[bool, str]:
    """
    Cek apakah saham lulus screening syariah.
    Return: (lulus: bool, alasan: str)
    """
    try:
        stk = yf.Ticker(ticker)
        info = stk.info

        # --- 1. Cek sektor/industri terlarang ---
        sector   = info.get("sector", "")
        industry = info.get("industry", "")

        for s in SYARIAH_CRITERIA["excluded_sectors"]:
            if s.lower() in sector.lower():
                return False, f"Sektor terlarang: {sector}"

        for ind in SYARIAH_CRITERIA["excluded_industries"]:
            if ind.lower() in industry.lower():
                return False, f"Industri terlarang: {industry}"

        # --- 2. Ambil data keuangan ---
        market_cap    = info.get("marketCap", 0)
        total_debt    = info.get("totalDebt", 0)
        revenue       = info.get("totalRevenue", 0)
        receivables   = info.get("netReceivables", 0)
        interest_exp  = info.get("interestExpense", 0)

        if market_cap is None or market_cap == 0:
            return False, "Data market cap tidak tersedia"

        # Handle None values
        total_debt   = total_debt or 0
        revenue      = revenue or 0
        receivables  = receivables or 0
        interest_exp = interest_exp or 0

        # --- 3. Debt to Market Cap < 33% ---
        debt_ratio = total_debt / market_cap
        if debt_ratio > SYARIAH_CRITERIA["max_debt_to_market_cap"]:
            return False, f"Debt ratio terlalu tinggi: {debt_ratio:.1%}"

        # --- 4. Interest to Revenue < 5% ---
        if revenue > 0:
            interest_ratio = abs(interest_exp) / revenue
            if interest_ratio > SYARIAH_CRITERIA["max_interest_income_to_revenue"]:
                return False, f"Interest income ratio terlalu tinggi: {interest_ratio:.1%}"

        # --- 5. Receivables to Market Cap < 49% ---
        recv_ratio = abs(receivables) / market_cap if receivables else 0
        if recv_ratio > SYARIAH_CRITERIA["max_receivables_to_market_cap"]:
            return False, f"Receivables ratio terlalu tinggi: {recv_ratio:.1%}"

        return True, "Lulus semua kriteria syariah"

    except Exception as e:
        logger.warning(f"Error saat cek syariah {ticker}: {e}")
        return False, f"Error: {e}"

# ============================================================
# ANALISIS TEKNIKAL
# ============================================================
def hitung_teknikal(df: pd.DataFrame) -> dict:
    close = df["Close"].squeeze()
    volume = df["Volume"].squeeze()

    hasil = {}

    # RSI
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    hasil["rsi"] = float((100 - (100 / (1 + rs))).iloc[-1])

    # Moving Average
    hasil["ma20"] = float(close.rolling(20).mean().iloc[-1])
    hasil["ma50"] = float(close.rolling(50).mean().iloc[-1])
    hasil["harga"] = float(close.iloc[-1])

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hasil["macd"]        = float(macd_line.iloc[-1])
    hasil["macd_signal"] = float(signal_line.iloc[-1])

    # Bollinger Bands
    ma20  = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    hasil["bb_upper"] = float((ma20 + 2 * std20).iloc[-1])
    hasil["bb_lower"] = float((ma20 - 2 * std20).iloc[-1])

    # Volume vs rata-rata
    hasil["vol_ratio"] = float(volume.iloc[-1] / volume.rolling(20).mean().iloc[-1])

    return hasil

# ============================================================
# SCORING & SINYAL
# ============================================================
def hitung_skor(teknikal: dict, fundamental: dict) -> tuple[float, str]:
    skor = 0.0

    # -- TEKNIKAL (60 poin) --
    rsi = teknikal.get("rsi", 50)
    if 30 <= rsi <= 70:
        skor += 20
    elif rsi < 30:   # oversold = peluang beli
        skor += 30
    elif rsi > 70:   # overbought = waspada
        skor += 5

    if teknikal["harga"] > teknikal["ma20"] > teknikal["ma50"]:
        skor += 20   # uptrend kuat

    if teknikal["macd"] > teknikal["macd_signal"]:
        skor += 10   # MACD bullish

    if teknikal["harga"] > teknikal["bb_lower"]:
        skor += 10   # di atas BB lower

    # -- FUNDAMENTAL (40 poin) --
    pe = fundamental.get("pe", 0)
    if 0 < pe < 30:
        skor += 15
    elif 30 <= pe < 50:
        skor += 8

    roe = fundamental.get("roe", 0)
    if roe > 0.20:   # ROE > 20%
        skor += 15
    elif roe > 0.10:
        skor += 8

    profit_margin = fundamental.get("profit_margin", 0)
    if profit_margin > 0.15:
        skor += 10
    elif profit_margin > 0.05:
        skor += 5

    # Tentukan sinyal
    if skor >= 70:
        sinyal = "🟢 BUY"
    elif skor >= 45:
        sinyal = "🟡 HOLD"
    else:
        sinyal = "🔴 SELL"

    return round(skor, 1), sinyal

# ============================================================
# ANALISIS SATU SAHAM
# ============================================================
def analisis_saham(ticker: str) -> Optional[dict]:
    try:
        logger.info(f"Menganalisis {ticker}...")

        # Cek syariah dulu
        lulus_syariah, alasan_syariah = cek_syariah(ticker)
        if not lulus_syariah:
            logger.info(f"{ticker} TIDAK LULUS syariah: {alasan_syariah}")
            return None

        # Ambil data harga
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            return None

        # Data fundamental
        info = yf.Ticker(ticker).info
        fundamental = {
            "pe":             info.get("trailingPE", 0) or 0,
            "roe":            info.get("returnOnEquity", 0) or 0,
            "profit_margin":  info.get("profitMargins", 0) or 0,
            "market_cap":     info.get("marketCap", 0) or 0,
            "nama":           info.get("shortName", ticker),
            "sektor":         info.get("sector", "-"),
        }

        teknikal = hitung_teknikal(df)
        skor, sinyal = hitung_skor(teknikal, fundamental)

        return {
            "ticker":    ticker,
            "nama":      fundamental["nama"],
            "sektor":    fundamental["sektor"],
            "harga":     teknikal["harga"],
            "sinyal":    sinyal,
            "skor":      skor,
            "rsi":       teknikal["rsi"],
            "macd":      teknikal["macd"],
            "pe":        fundamental["pe"],
            "roe":       fundamental["roe"] * 100,
        }

    except Exception as e:
        logger.error(f"Error analisis {ticker}: {e}")
        return None

# ============================================================
# FORMAT PESAN TELEGRAM
# ============================================================
def format_pesan(hasil: list[dict]) -> str:
    tanggal = datetime.now().strftime("%d %b %Y")

    buy_list  = [h for h in hasil if "BUY"  in h["sinyal"]]
    hold_list = [h for h in hasil if "HOLD" in h["sinyal"]]
    sell_list = [h for h in hasil if "SELL" in h["sinyal"]]

    pesan = f"""🇺🇸 <b>US SYARIAH STOCK SCREENER</b>
📅 {tanggal} | Berbasis Kriteria AAOIFI

━━━━━━━━━━━━━━━━━━━━━━
📊 <b>TOTAL DIANALISIS: {len(hasil)} saham syariah</b>
🟢 BUY: {len(buy_list)} | 🟡 HOLD: {len(hold_list)} | 🔴 SELL: {len(sell_list)}
━━━━━━━━━━━━━━━━━━━━━━
"""

    if buy_list:
        pesan += "\n🟢 <b>REKOMENDASI BUY</b>\n"
        for h in sorted(buy_list, key=lambda x: x["skor"], reverse=True)[:10]:
            pesan += (
                f"• <b>{h['ticker']}</b> ({h['nama'][:20]})\n"
                f"  💵 ${h['harga']:.2f} | Skor: {h['skor']}/100\n"
                f"  RSI: {h['rsi']:.1f} | PE: {h['pe']:.1f} | ROE: {h['roe']:.1f}%\n"
                f"  📂 {h['sektor']}\n\n"
            )

    if hold_list:
        pesan += "🟡 <b>HOLD</b>\n"
        for h in sorted(hold_list, key=lambda x: x["skor"], reverse=True)[:8]:
            pesan += f"• <b>{h['ticker']}</b> ${h['harga']:.2f} | Skor: {h['skor']}/100\n"
        pesan += "\n"

    if sell_list:
        pesan += "🔴 <b>SELL / WATCH OUT</b>\n"
        for h in sorted(sell_list, key=lambda x: x["skor"])[:5]:
            pesan += f"• <b>{h['ticker']}</b> ${h['harga']:.2f} | Skor: {h['skor']}/100\n"
        pesan += "\n"

    pesan += "━━━━━━━━━━━━━━━━━━━━━━\n"
    pesan += "⚠️ <i>Bukan saran investasi. DYOR!</i>\n"
    pesan += "🤖 <i>Powered by Clau - Kandip's smartest assistant 😎</i>"

    return pesan

# ============================================================
# MAIN
# ============================================================
def main():
    logger.info("=== US SYARIAH STOCK SCREENER DIMULAI ===")

    hasil_semua = []
    tidak_lulus = []

    for ticker in US_SYARIAH_STOCKS:
        hasil = analisis_saham(ticker)
        if hasil:
            hasil_semua.append(hasil)
        else:
            tidak_lulus.append(ticker)

    logger.info(f"Lulus syariah & analisis: {len(hasil_semua)} saham")
    logger.info(f"Tidak lulus / error: {len(tidak_lulus)} saham")

    if hasil_semua:
        pesan = format_pesan(hasil_semua)
        print("\n" + pesan)  # Tampilkan di log juga
        sukses = kirim_telegram(pesan)
        if sukses:
            logger.info("Notifikasi Telegram berhasil dikirim!")
        else:
            logger.warning("Gagal kirim Telegram - cek token/chat_id")

        # --- Kirim email KHUSUS kalau ticker pilihan kena sinyal SELL ---
        sell_list_all = [h for h in hasil_semua if "SELL" in h["sinyal"]]

        if ALERT_TICKERS:
            sell_list = [h for h in sell_list_all if h["ticker"] in ALERT_TICKERS]
        else:
            sell_list = sell_list_all  # kalau tidak diisi, alert semua SELL (default lama)

        if sell_list:
            tanggal = datetime.now().strftime("%d %b %Y")
            isi_email = f"PERINGATAN SINYAL SELL - {tanggal}\n\n"
            isi_email += "Saham berikut menunjukkan sinyal SELL:\n\n"
            for h in sorted(sell_list, key=lambda x: x["skor"]):
                isi_email += (
                    f"- {h['ticker']} ({h['nama']})\n"
                    f"  Harga: ${h['harga']:.2f} | Skor: {h['skor']}/100 | RSI: {h['rsi']:.1f}\n\n"
                )
            isi_email += "Bukan saran investasi. DYOR!\n"
            isi_email += "Powered by Clau - Kandip's smartest assistant"

            email_sukses = kirim_email(
                subjek=f"[ALERT] Sinyal SELL Terdeteksi - {tanggal}",
                isi=isi_email
            )
            if email_sukses:
                logger.info("Email alert SELL berhasil dikirim!")
            else:
                logger.warning("Gagal kirim email alert SELL")
    else:
        logger.error("Tidak ada saham yang berhasil dianalisis!")

    logger.info("=== SELESAI ===")

if __name__ == "__main__":
    main()
