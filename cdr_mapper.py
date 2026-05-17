import os
import re
import threading
import requests
import pdfplumber
import customtkinter as ctk
from collections import Counter, defaultdict
from tkintermapview import TkinterMapView
from tkinter import filedialog, messagebox
import tkinter as tk
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import networkx as nx
from fpdf import FPDF

load_dotenv()
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DARK_BG = "#1e1e2e"
CHART_BG = "#2a2a3e"
ACCENT = "#4f8ef7"
COLORS = ["#4f8ef7", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]


def _embed_chart(parent, fig):
    """Embed a matplotlib figure into a CTkFrame, clearing old widgets first."""
    for w in parent.winfo_children():
        w.destroy()
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
    plt.close(fig)


class CDRMapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CDR Intelligence Mapper v2")
        self.geometry("1500x950")

        self.markers = []
        self.results_data = []
        self.last_usage_report = None
        self.cdr_df = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_tabs()

    # ──────────────────────────────────────────────────────────
    # SIDEBAR
    # ──────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=300, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(11, weight=1)
        self.sidebar_frame = sb

        r = 0
        ctk.CTkLabel(sb, text="🛰️ CDR MAPPER v2",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).grid(row=r, column=0, padx=20, pady=(20, 2)); r += 1
        ctk.CTkLabel(sb, text="CDR Intelligence Dashboard",
                     font=ctk.CTkFont(size=11), text_color="gray"
                     ).grid(row=r, column=0, padx=20, pady=(0, 14)); r += 1

        ctk.CTkLabel(sb, text="Unwired Labs API Token:",
                     font=ctk.CTkFont(size=13)
                     ).grid(row=r, column=0, padx=20, pady=(4, 0), sticky="w"); r += 1
        self.api_entry = ctk.CTkEntry(sb, placeholder_text="Enter API Token", show="*")
        self.api_entry.grid(row=r, column=0, padx=20, pady=(4, 10), sticky="ew")
        env_token = os.getenv("UNWIRED_TOKEN", "")
        if env_token:
            self.api_entry.insert(0, env_token)
        r += 1

        ctk.CTkButton(sb, text="📂  Load PDF / CSV", command=self.load_file,
                      height=42, font=ctk.CTkFont(size=13, weight="bold")
                      ).grid(row=r, column=0, padx=20, pady=8, sticky="ew"); r += 1

        self.stats_label = ctk.CTkLabel(
            sb, text="Towers: 0  |  Mapped: 0\nCDR Records: 0",
            justify="left", font=ctk.CTkFont(size=12))
        self.stats_label.grid(row=r, column=0, padx=20, pady=4, sticky="w"); r += 1

        ctk.CTkButton(sb, text="⚡  Map Towers from .env",
                      command=self.quick_map_env,
                      fg_color="#2ecc71", hover_color="#27ae60"
                      ).grid(row=r, column=0, padx=20, pady=6, sticky="ew"); r += 1

        self.progress_bar = ctk.CTkProgressBar(sb)
        self.progress_bar.grid(row=r, column=0, padx=20, pady=4, sticky="ew")
        self.progress_bar.set(0); r += 1

        self.status_label = ctk.CTkLabel(sb, text="Ready",
                                         font=ctk.CTkFont(size=11), text_color="gray")
        self.status_label.grid(row=r, column=0, padx=20, pady=(0, 4)); r += 1

        ctk.CTkButton(sb, text="🗑️  Clear All", command=self.clear_all,
                      fg_color="transparent", border_width=2
                      ).grid(row=r, column=0, padx=20, pady=8, sticky="ew"); r += 1

        self.list_frame = ctk.CTkScrollableFrame(sb, label_text="Detected Towers", height=200)
        self.list_frame.grid(row=r, column=0, padx=20, pady=10, sticky="nsew")

    # ──────────────────────────────────────────────────────────
    # TABS
    # ──────────────────────────────────────────────────────────

    def _build_tabs(self):
        self.tab_view = ctk.CTkTabview(self, corner_radius=8)
        self.tab_view.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")
        for t in ["Map", "Overview", "Analytics", "Timeline", "Alerts", "Network", "Report"]:
            self.tab_view.add(t)
        self._build_map_tab()
        self._build_overview_tab()
        self._build_analytics_tab()
        self._build_timeline_tab()
        self._build_alerts_tab()
        self._build_network_tab()
        self._build_report_tab()

    def _build_map_tab(self):
        f = self.tab_view.tab("Map")
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        self.map_widget = TkinterMapView(f, corner_radius=10)
        self.map_widget.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.map_widget.set_position(20.5937, 78.9629)
        self.map_widget.set_zoom(5)

    def _build_overview_tab(self):
        f = self.tab_view.tab("Overview")
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text="CDR Overview & Insights",
                     font=ctk.CTkFont(size=18, weight="bold")
                     ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        self.insights_text = ctk.CTkTextbox(f, wrap="word", font=ctk.CTkFont(size=13))
        self.insights_text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.insights_text.insert("1.0", "Load a PDF or CSV file to see CDR insights.\n")
        self.insights_text.configure(state="disabled")

    def _build_analytics_tab(self):
        f = self.tab_view.tab("Analytics")
        f.grid_rowconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        self.an_pie   = ctk.CTkFrame(f); self.an_pie.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.an_bar   = ctk.CTkFrame(f); self.an_bar.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self.an_dur   = ctk.CTkFrame(f); self.an_dur.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        self.an_hour  = ctk.CTkFrame(f); self.an_hour.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        for frm in [self.an_pie, self.an_bar, self.an_dur, self.an_hour]:
            ctk.CTkLabel(frm, text="Load a CDR file to populate.", text_color="gray").pack(expand=True)

    def _build_timeline_tab(self):
        f = self.tab_view.tab("Timeline")
        f.grid_rowconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        self.tl_daily    = ctk.CTkFrame(f); self.tl_daily.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.tl_type     = ctk.CTkFrame(f); self.tl_type.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self.tl_dur      = ctk.CTkFrame(f); self.tl_dur.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        self.tl_contacts = ctk.CTkFrame(f); self.tl_contacts.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        for frm in [self.tl_daily, self.tl_type, self.tl_dur, self.tl_contacts]:
            ctk.CTkLabel(frm, text="Load a CDR file to populate.", text_color="gray").pack(expand=True)

    def _build_alerts_tab(self):
        f = self.tab_view.tab("Alerts")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(3, weight=1)

        # Search row
        sr = ctk.CTkFrame(f, fg_color="transparent")
        sr.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="ew")
        sr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sr, text="🔍  Search Number:",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        self.search_entry = ctk.CTkEntry(sr, placeholder_text="Enter phone number...")
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(sr, text="Search", width=100,
                      command=self.run_search).grid(row=1, column=1, padx=(8, 0), pady=(4, 0))

        self.search_result = ctk.CTkTextbox(f, height=130, wrap="word", font=ctk.CTkFont(size=12))
        self.search_result.grid(row=1, column=0, padx=16, pady=(4, 8), sticky="ew")
        self.search_result.insert("1.0", "Search results will appear here.\n")
        self.search_result.configure(state="disabled")

        ctk.CTkLabel(f, text="⚠️  Suspicious Activity Alerts",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=2, column=0, padx=16, pady=(4, 0), sticky="w")

        self.alerts_text = ctk.CTkTextbox(f, wrap="word", font=ctk.CTkFont(size=12))
        self.alerts_text.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="nsew")
        self.alerts_text.insert("1.0", "No alerts yet. Load a CDR file.\n")
        self.alerts_text.configure(state="disabled")

    def _build_network_tab(self):
        f = self.tab_view.tab("Network")
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)
        self.net_heat = ctk.CTkFrame(f); self.net_heat.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.net_graph = ctk.CTkFrame(f); self.net_graph.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        ctk.CTkLabel(self.net_heat,  text="Load CDR file for heatmap.",  text_color="gray").pack(expand=True)
        ctk.CTkLabel(self.net_graph, text="Load CDR file for network graph.", text_color="gray").pack(expand=True)

    def _build_report_tab(self):
        f = self.tab_view.tab("Report")
        f.grid_rowconfigure(1, weight=1)
        f.grid_columnconfigure(0, weight=1)

        br = ctk.CTkFrame(f, fg_color="transparent")
        br.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        ctk.CTkLabel(br, text="📄  Forensic Report",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(br, text="⬇  Export PDF", width=150,
                      command=lambda: self.export_report("pdf")).pack(side="right", padx=(8, 0))
        ctk.CTkButton(br, text="⬇  Export TXT", width=150,
                      command=lambda: self.export_report("txt")).pack(side="right")

        self.report_text = ctk.CTkTextbox(f, wrap="word", font=ctk.CTkFont(size=12))
        self.report_text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.report_text.insert("1.0", "Load a CDR file to generate a report.\n")
        self.report_text.configure(state="disabled")

    # ──────────────────────────────────────────────────────────
    # FILE LOADING
    # ──────────────────────────────────────────────────────────

    def load_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("CDR Files", "*.pdf *.csv"), ("PDF", "*.pdf"), ("CSV", "*.csv")])
        if not file_path:
            return

        token = self.api_entry.get()
        self.progress_bar.set(0)
        self.results_data = []
        self._set_status("Loading…")

        try:
            towers = []
            usage_report = None

            if file_path.lower().endswith('.pdf'):
                towers = self.extract_pdf_data(file_path)
                usage_report = self.extract_usage_data(file_path)
                if usage_report:
                    self.display_usage_report(usage_report)
                    self._build_df_from_pdf(usage_report)
                    self._render_all_charts()
                    self.tab_view.set("Overview")

            elif file_path.lower().endswith('.csv'):
                towers = self.extract_csv_data(file_path)
                self._load_cdr_csv(file_path)
                self._render_all_charts()
                self.tab_view.set("Analytics")
            else:
                messagebox.showerror("Unsupported", "Only PDF and CSV files are supported.")
                return

            cdr_count = len(self.cdr_df) if self.cdr_df is not None else 0
            self.stats_label.configure(
                text=f"Towers: {len(towers)}  |  Mapped: 0\nCDR Records: {cdr_count}")

            if towers and token:
                self._set_status("Resolving tower locations…")
                threading.Thread(target=self.resolve_locations,
                                 args=(towers, token), daemon=True).start()
            elif towers and not token:
                messagebox.showwarning("Token Missing",
                                       "Enter your Unwired Labs token to map towers.")
            elif not towers and not usage_report and self.cdr_df is None:
                messagebox.showinfo("No Data", "No recognisable data found in the file.")

            self._set_status("Done.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process file:\n{e}")
            self._set_status("Error.")

    def _set_status(self, msg):
        self.status_label.configure(text=msg)
        self.update_idletasks()

    # ──────────────────────────────────────────────────────────
    # DATA EXTRACTION
    # ──────────────────────────────────────────────────────────

    def _load_cdr_csv(self, file_path):
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.strip().lower() for c in df.columns]
            rename = {}
            for col in df.columns:
                if col in ('phone','mobile','msisdn','called','caller','number','b_party'):
                    rename[col] = 'number'
                elif col in ('type','call_type','calltype','direction','category'):
                    rename[col] = 'call_type'
                elif col in ('duration','dur','seconds','duration_sec','call_duration'):
                    rename[col] = 'duration'
                elif col in ('date','call_date','calldate','start_date'):
                    rename[col] = 'date'
                elif col in ('time','call_time','calltime','start_time'):
                    rename[col] = 'time'
            df.rename(columns=rename, inplace=True)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            if 'time' in df.columns:
                df['hour'] = pd.to_datetime(df['time'], errors='coerce').dt.hour
            elif 'date' in df.columns:
                df['hour'] = df['date'].dt.hour
            self.cdr_df = df
        except Exception as e:
            print(f"CSV load error: {e}")
            self.cdr_df = None

    def _build_df_from_pdf(self, report):
        rows = []
        for r in report.get("voice_rows", []):
            rows.append({"number": r["number"], "call_type": "outgoing",
                         "duration": r["seconds"],
                         "date": pd.to_datetime(r["date"], format="%d-%b-%y", errors="coerce"),
                         "time": r["time"]})
        for r in report.get("sms_rows", []):
            rows.append({"number": r["number"], "call_type": "sms",
                         "duration": 0,
                         "date": pd.to_datetime(r["date"], format="%d-%b-%y", errors="coerce"),
                         "time": r["time"]})
        if rows:
            df = pd.DataFrame(rows)
            df['hour'] = pd.to_datetime(df['time'], format="%H:%M:%S", errors='coerce').dt.hour
            self.cdr_df = df
        else:
            self.cdr_df = None

    def extract_csv_data(self, file_path):
        towers = []
        try:
            df = pd.read_csv(file_path)
            cols = [str(c).lower() for c in df.columns]
            mcc_idx = mnc_idx = lac_idx = cid_idx = -1
            for i, col in enumerate(cols):
                if 'mcc' in col: mcc_idx = i
                elif 'mnc' in col: mnc_idx = i
                elif 'lac' in col or 'tac' in col: lac_idx = i
                elif 'cid' in col or 'cellid' in col or 'cell' in col: cid_idx = i
            if mcc_idx != -1 and mnc_idx != -1 and lac_idx != -1 and cid_idx != -1:
                for _, row in df.iterrows():
                    try:
                        towers.append({'mcc': int(str(row.iloc[mcc_idx]).strip()),
                                       'mnc': int(str(row.iloc[mnc_idx]).strip()),
                                       'lac': int(str(row.iloc[lac_idx]).strip()),
                                       'cid': int(str(row.iloc[cid_idx]).strip())})
                    except: pass
            else:
                text = df.to_string()
                regex = r'(MCC[:\s-]*)?(\d{3})[,\s-]+(MNC[:\s-]*)?(\d{2,3})[,\s-]+(LAC[:\s-]*)?(\d{2,5})[,\s-]+(CID[:\s-]*)?(\d{2,10})'
                for m in re.finditer(regex, text, re.IGNORECASE):
                    towers.append({'mcc': int(m.group(2)), 'mnc': int(m.group(4)),
                                   'lac': int(m.group(6)), 'cid': int(m.group(8))})
        except Exception as e:
            print(f"CSV tower parse error: {e}")
        unique = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique.values())

    def extract_usage_data(self, file_path):
        voice_rows, sms_rows, mode = [], [], None
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    cl = line.strip()
                    if "2.0 Voice" in cl: mode = "voice"; continue
                    if "3.0 SMS"   in cl: mode = "sms";   continue
                    if re.search(r"^\s*(Subtotal|Usage in India Total|Voice Total|SMS Total|Page)\b", cl):
                        continue
                    m = re.match(
                        r"^\s*\d+\s+(\d{2}-[A-Z]{3}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+((?:\+?91)?[6-9]\d{9})\s+(.+)$", cl)
                    if not m: continue
                    vals = m.group(4).split()
                    if mode == "voice" and len(vals) >= 5:
                        try:
                            voice_rows.append({"date": m.group(1), "time": m.group(2),
                                               "number": self.normalize_phone(m.group(3)),
                                               "seconds": int(vals[0])})
                        except ValueError: pass
                    elif mode == "sms" and len(vals) >= 4:
                        try:
                            sms_rows.append({"date": m.group(1), "time": m.group(2),
                                             "number": self.normalize_phone(m.group(3)),
                                             "count": int(vals[0])})
                        except ValueError: pass
        if not voice_rows and not sms_rows:
            return None
        return {"voice_rows": voice_rows, "sms_rows": sms_rows}

    def extract_pdf_data(self, file_path):
        towers = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    df = pd.DataFrame(table)
                    if df.empty: continue
                    first = [str(x).lower() for x in df.iloc[0]]
                    mi = mni = li = ci = -1
                    for i, c in enumerate(first):
                        if 'mcc' in c: mi = i
                        elif 'mnc' in c: mni = i
                        elif 'lac' in c or 'tac' in c: li = i
                        elif 'cid' in c or 'cellid' in c or 'cell' in c: ci = i
                    if mi != -1 and mni != -1 and li != -1 and ci != -1:
                        for idx, row in df.iterrows():
                            if idx == 0: continue
                            try:
                                towers.append({'mcc': int(str(row[mi]).strip()),
                                               'mnc': int(str(row[mni]).strip()),
                                               'lac': int(str(row[li]).strip()),
                                               'cid': int(str(row[ci]).strip())})
                            except: pass
                text = page.extract_text() or ""
                regex = r'(MCC[:\s-]*)?(\d{3})[,\s-]+(MNC[:\s-]*)?(\d{2,3})[,\s-]+(LAC[:\s-]*)?(\d{2,5})[,\s-]+(CID[:\s-]*)?(\d{2,10})'
                for m in re.finditer(regex, text, re.IGNORECASE):
                    towers.append({'mcc': int(m.group(2)), 'mnc': int(m.group(4)),
                                   'lac': int(m.group(6)), 'cid': int(m.group(8))})
        unique = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique.values())

    def normalize_phone(self, number):
        digits = re.sub(r"\D", "", number)
        return f"91{digits}" if len(digits) == 10 else digits

    def format_duration(self, seconds):
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h: return f"{h}h {m}m {s}s"
        if m: return f"{m}m {s}s"
        return f"{s}s"

    # ──────────────────────────────────────────────────────────
    # OVERVIEW TEXT REPORT
    # ──────────────────────────────────────────────────────────

    def display_usage_report(self, report):
        self.last_usage_report = report
        vr = report["voice_rows"]
        sr = report["sms_rows"]

        call_counts      = Counter(r["number"] for r in vr)
        dur_by_num       = defaultdict(int)
        calls_by_day     = Counter()
        for r in vr:
            dur_by_num[r["number"]] += r["seconds"]
            calls_by_day[r["date"]] += 1

        sms_counts  = Counter()
        sms_by_day  = Counter()
        for r in sr:
            sms_counts[r["number"]] += r["count"]
            sms_by_day[r["date"]]   += r["count"]

        total_secs   = sum(r["seconds"] for r in vr)
        longest      = sorted(vr, key=lambda r: r["seconds"], reverse=True)[:10]

        lines = [
            "═" * 50,
            "  CDR USAGE INSIGHTS",
            "═" * 50,
            f"  Voice calls        : {len(vr)}",
            f"  Unique numbers     : {len(call_counts)}",
            f"  Total call duration: {self.format_duration(total_secs)}",
            f"  SMS records        : {len(sr)}",
            f"  Total SMS count    : {sum(r['count'] for r in sr)}",
            f"  Unique SMS numbers : {len(sms_counts)}",
            "",
            "── Most Called Numbers ──────────────────────",
        ]
        for num, cnt in call_counts.most_common(10):
            lines.append(f"  {num}  →  {cnt} calls")

        lines += ["", "── Highest Total Duration ───────────────────"]
        for num, secs in sorted(dur_by_num.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"  {num}  →  {self.format_duration(secs)}")

        lines += ["", "── Longest Individual Calls ─────────────────"]
        for r in longest:
            lines.append(f"  {r['date']} {r['time']}  |  {r['number']}  |  {self.format_duration(r['seconds'])}")

        lines += ["", "── SMS Summary ──────────────────────────────"]
        if sr:
            for num, cnt in sms_counts.most_common(10):
                lines.append(f"  {num}  →  {cnt} SMS")
        else:
            lines.append("  No SMS records found.")

        lines += ["", "── Calls By Day ─────────────────────────────"]
        for day, cnt in sorted(calls_by_day.items()):
            lines.append(f"  {day}  →  {cnt} calls")

        if sms_by_day:
            lines += ["", "── SMS By Day ───────────────────────────────"]
            for day, cnt in sorted(sms_by_day.items()):
                lines.append(f"  {day}  →  {cnt} SMS")

        self.insights_text.configure(state="normal")
        self.insights_text.delete("1.0", "end")
        self.insights_text.insert("1.0", "\n".join(lines))
        self.insights_text.configure(state="disabled")


    # ──────────────────────────────────────────────────────────
    # CHART RENDERING
    # ──────────────────────────────────────────────────────────

    def _render_all_charts(self):
        if self.cdr_df is None:
            return
        self._chart_pie()
        self._chart_bar()
        self._chart_duration()
        self._chart_hourly()
        self._chart_daily()
        self._chart_type_timeline()
        self._chart_duration_timeline()
        self._chart_top_contacts_timeline()
        self._chart_heatmap()
        self._chart_network()
        self._build_alerts()
        self._build_report_text()

    def _make_fig(self, title=""):
        fig = Figure(figsize=(5, 3.2), dpi=96, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        ax.tick_params(colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
        if title:
            ax.set_title(title, color="white", fontsize=10, pad=6)
        fig.tight_layout(pad=1.5)
        return fig, ax

    def _chart_pie(self):
        df = self.cdr_df
        if 'call_type' not in df.columns:
            return
        counts = df['call_type'].value_counts()
        fig, ax = self._make_fig("Call Type Distribution")
        wedges, texts, autotexts = ax.pie(
            counts.values, labels=counts.index,
            autopct="%1.1f%%", colors=COLORS[:len(counts)],
            textprops={"color": "white", "fontsize": 8},
            wedgeprops={"linewidth": 0.5, "edgecolor": CHART_BG}
        )
        for at in autotexts:
            at.set_color("white")
        _embed_chart(self.an_pie, fig)

    def _chart_bar(self):
        df = self.cdr_df
        if 'call_type' not in df.columns:
            return
        counts = df['call_type'].value_counts()
        fig, ax = self._make_fig("Call Type Frequency")
        bars = ax.bar(counts.index, counts.values,
                      color=COLORS[:len(counts)], edgecolor=CHART_BG, linewidth=0.5)
        ax.set_xlabel("Call Type", color="white", fontsize=8)
        ax.set_ylabel("Count", color="white", fontsize=8)
        ax.tick_params(axis='x', rotation=20)
        for bar, val in zip(bars, counts.values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    str(val), ha='center', va='bottom', color='white', fontsize=7)
        _embed_chart(self.an_bar, fig)

    def _chart_duration(self):
        df = self.cdr_df
        if 'duration' not in df.columns or 'number' not in df.columns:
            return
        top = df.groupby('number')['duration'].sum().nlargest(10)
        fig, ax = self._make_fig("Top 10 — Total Call Duration (s)")
        labels = [n[-10:] for n in top.index]
        ax.barh(labels, top.values, color=ACCENT)
        ax.set_xlabel("Seconds", color="white", fontsize=8)
        ax.invert_yaxis()
        _embed_chart(self.an_dur, fig)

    def _chart_hourly(self):
        df = self.cdr_df
        if 'hour' not in df.columns:
            return
        counts = df['hour'].value_counts().sort_index()
        all_hours = range(24)
        vals = [counts.get(h, 0) for h in all_hours]
        fig, ax = self._make_fig("Hourly Communication Activity")
        ax.bar(list(all_hours), vals, color=ACCENT, edgecolor=CHART_BG)
        ax.set_xlabel("Hour of Day", color="white", fontsize=8)
        ax.set_ylabel("Calls", color="white", fontsize=8)
        ax.set_xticks(list(all_hours))
        ax.tick_params(axis='x', labelsize=6)
        _embed_chart(self.an_hour, fig)

    def _chart_daily(self):
        df = self.cdr_df
        if 'date' not in df.columns:
            return
        daily = df.groupby(df['date'].dt.date).size()
        fig, ax = self._make_fig("Daily Communication Trend")
        ax.plot(list(daily.index), list(daily.values),
                color=ACCENT, linewidth=1.5, marker='o', markersize=3)
        ax.fill_between(list(daily.index), list(daily.values),
                        alpha=0.15, color=ACCENT)
        ax.set_xlabel("Date", color="white", fontsize=8)
        ax.set_ylabel("Calls", color="white", fontsize=8)
        fig.autofmt_xdate(rotation=30)
        _embed_chart(self.tl_daily, fig)

    def _chart_type_timeline(self):
        df = self.cdr_df
        if 'date' not in df.columns or 'call_type' not in df.columns:
            return
        fig, ax = self._make_fig("Call Type Over Time")
        for i, ctype in enumerate(df['call_type'].unique()):
            sub = df[df['call_type'] == ctype].groupby(df['date'].dt.date).size()
            ax.plot(list(sub.index), list(sub.values),
                    label=ctype, color=COLORS[i % len(COLORS)], linewidth=1.2, marker='o', markersize=2)
        ax.legend(fontsize=7, labelcolor='white',
                  facecolor=CHART_BG, edgecolor='#444')
        ax.set_xlabel("Date", color="white", fontsize=8)
        fig.autofmt_xdate(rotation=30)
        _embed_chart(self.tl_type, fig)

    def _chart_duration_timeline(self):
        df = self.cdr_df
        if 'date' not in df.columns or 'duration' not in df.columns:
            return
        daily_dur = df.groupby(df['date'].dt.date)['duration'].sum()
        fig, ax = self._make_fig("Duration Variation Over Time (s)")
        ax.plot(list(daily_dur.index), list(daily_dur.values),
                color="#e74c3c", linewidth=1.5, marker='o', markersize=3)
        ax.fill_between(list(daily_dur.index), list(daily_dur.values),
                        alpha=0.15, color="#e74c3c")
        ax.set_xlabel("Date", color="white", fontsize=8)
        ax.set_ylabel("Total Seconds", color="white", fontsize=8)
        fig.autofmt_xdate(rotation=30)
        _embed_chart(self.tl_dur, fig)

    def _chart_top_contacts_timeline(self):
        df = self.cdr_df
        if 'date' not in df.columns or 'number' not in df.columns:
            return
        top5 = df['number'].value_counts().head(5).index.tolist()
        fig, ax = self._make_fig("Top 5 Contacts Over Time")
        for i, num in enumerate(top5):
            sub = df[df['number'] == num].groupby(df['date'].dt.date).size()
            ax.plot(list(sub.index), list(sub.values),
                    label=str(num)[-10:], color=COLORS[i % len(COLORS)],
                    linewidth=1.2, marker='o', markersize=2)
        ax.legend(fontsize=7, labelcolor='white',
                  facecolor=CHART_BG, edgecolor='#444')
        ax.set_xlabel("Date", color="white", fontsize=8)
        fig.autofmt_xdate(rotation=30)
        _embed_chart(self.tl_contacts, fig)

    def _chart_heatmap(self):
        df = self.cdr_df
        if 'date' not in df.columns or 'hour' not in df.columns:
            return
        df2 = df.copy()
        df2['dow'] = df2['date'].dt.dayofweek
        pivot = df2.groupby(['dow', 'hour']).size().unstack(fill_value=0)
        # Ensure all 24 hours present
        for h in range(24):
            if h not in pivot.columns:
                pivot[h] = 0
        pivot = pivot[sorted(pivot.columns)]
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        matrix = np.zeros((7, 24))
        for i in range(7):
            if i in pivot.index:
                matrix[i] = [pivot.loc[i, h] for h in range(24)]

        fig = Figure(figsize=(5, 3.2), dpi=96, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        im = ax.imshow(matrix, aspect='auto', cmap='Blues', interpolation='nearest')
        ax.set_xticks(range(24))
        ax.set_xticklabels([str(h) for h in range(24)], fontsize=6, color='white')
        ax.set_yticks(range(7))
        ax.set_yticklabels(days, fontsize=8, color='white')
        ax.set_title("Communication Heatmap (Day × Hour)", color='white', fontsize=10)
        fig.colorbar(im, ax=ax).ax.yaxis.set_tick_params(color='white', labelcolor='white')
        fig.tight_layout(pad=1.5)
        _embed_chart(self.net_heat, fig)

    def _chart_network(self):
        df = self.cdr_df
        if 'number' not in df.columns:
            return
        top = df['number'].value_counts().head(12).index.tolist()
        df2 = df[df['number'].isin(top)]
        G = nx.Graph()
        owner = "SUBJECT"
        G.add_node(owner)
        edge_weights = Counter()
        for num, grp in df2.groupby('number'):
            edge_weights[(owner, str(num))] += len(grp)
        for (u, v), w in edge_weights.items():
            G.add_edge(u, v, weight=w)

        fig = Figure(figsize=(5, 3.2), dpi=96, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        ax.axis('off')
        ax.set_title("Communication Network Graph", color='white', fontsize=10)

        pos = nx.spring_layout(G, seed=42, k=1.2)
        weights = [G[u][v]['weight'] for u, v in G.edges()]
        max_w = max(weights) if weights else 1
        norm_w = [1 + 4 * (w / max_w) for w in weights]

        node_colors = [ACCENT if n == owner else "#e74c3c" for n in G.nodes()]
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                               node_size=400, alpha=0.9)
        nx.draw_networkx_edges(G, pos, ax=ax, width=norm_w,
                               edge_color="#aaaaaa", alpha=0.6)
        labels = {n: n[-8:] if n != owner else owner for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, ax=ax,
                                font_size=6, font_color='white')
        fig.tight_layout(pad=1.0)
        _embed_chart(self.net_graph, fig)

    # ──────────────────────────────────────────────────────────
    # ALERTS & SEARCH
    # ──────────────────────────────────────────────────────────

    def _build_alerts(self):
        df = self.cdr_df
        if df is None or 'number' not in df.columns:
            return

        alerts = []
        call_counts = df['number'].value_counts()

        # High frequency threshold: mean + 2*std
        threshold_freq = call_counts.mean() + 2 * call_counts.std()
        for num, cnt in call_counts.items():
            if cnt >= threshold_freq:
                alerts.append(f"🔴 HIGH FREQUENCY  |  {num}  |  {int(cnt)} interactions  "
                               f"(threshold: {int(threshold_freq)})")

        # Long duration threshold
        if 'duration' in df.columns:
            dur_by_num = df.groupby('number')['duration'].sum()
            threshold_dur = dur_by_num.mean() + 2 * dur_by_num.std()
            for num, secs in dur_by_num.items():
                if secs >= threshold_dur:
                    alerts.append(f"🟠 LONG DURATION   |  {num}  |  "
                                   f"{self.format_duration(secs)}  "
                                   f"(threshold: {self.format_duration(int(threshold_dur))})")

        # Night activity (00:00 – 05:00)
        if 'hour' in df.columns:
            night = df[df['hour'].between(0, 4)]
            night_counts = night['number'].value_counts()
            for num, cnt in night_counts.items():
                if cnt >= 5:
                    alerts.append(f"🌙 NIGHT ACTIVITY  |  {num}  |  {int(cnt)} calls between 00:00–05:00")

        self.alerts_text.configure(state="normal")
        self.alerts_text.delete("1.0", "end")
        if alerts:
            self.alerts_text.insert("1.0",
                f"⚠️  {len(alerts)} alert(s) detected\n" + "─" * 55 + "\n\n" +
                "\n\n".join(alerts))
        else:
            self.alerts_text.insert("1.0", "✅  No suspicious activity detected.")
        self.alerts_text.configure(state="disabled")

    def run_search(self):
        df = self.cdr_df
        query = self.search_entry.get().strip()
        self.search_result.configure(state="normal")
        self.search_result.delete("1.0", "end")

        if df is None or 'number' not in df.columns:
            self.search_result.insert("1.0", "No CDR data loaded.")
            self.search_result.configure(state="disabled")
            return
        if not query:
            self.search_result.insert("1.0", "Enter a number to search.")
            self.search_result.configure(state="disabled")
            return

        # Partial match
        matches = df[df['number'].astype(str).str.contains(query, na=False)]
        if matches.empty:
            self.search_result.insert("1.0", f"No records found for: {query}")
        else:
            lines = [f"Results for: {query}  ({len(matches)} records)\n"]
            if 'call_type' in matches.columns:
                lines.append("Call types: " + str(dict(matches['call_type'].value_counts())))
            if 'duration' in matches.columns:
                lines.append(f"Total duration: {self.format_duration(matches['duration'].sum())}")
            if 'date' in matches.columns:
                lines.append(f"Date range: {matches['date'].min().date()} → {matches['date'].max().date()}")
            lines.append("\nRecent records:")
            for _, row in matches.head(10).iterrows():
                date_str = str(row.get('date', ''))[:10]
                num  = row.get('number', '')
                ctype = row.get('call_type', '')
                dur  = self.format_duration(row['duration']) if 'duration' in row else ''
                lines.append(f"  {date_str}  {num}  {ctype}  {dur}")
            self.search_result.insert("1.0", "\n".join(lines))

        self.search_result.configure(state="disabled")

    # ──────────────────────────────────────────────────────────
    # REPORT GENERATION & EXPORT
    # ──────────────────────────────────────────────────────────

    def _build_report_text(self):
        df = self.cdr_df
        lines = [
            "═" * 55,
            "   CDR FORENSIC INTELLIGENCE REPORT",
            f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "═" * 55, "",
        ]

        if df is not None:
            lines += [
                f"Total Records      : {len(df)}",
                f"Unique Numbers     : {df['number'].nunique() if 'number' in df.columns else 'N/A'}",
            ]
            if 'call_type' in df.columns:
                lines.append(f"Call Types         : {dict(df['call_type'].value_counts())}")
            if 'duration' in df.columns:
                lines.append(f"Total Duration     : {self.format_duration(df['duration'].sum())}")
                lines.append(f"Avg Duration       : {self.format_duration(int(df['duration'].mean()))}")
            if 'date' in df.columns:
                lines.append(f"Date Range         : {df['date'].min().date()} → {df['date'].max().date()}")
            if 'number' in df.columns:
                lines += ["", "── Top 10 Most Active Numbers ──────────────"]
                for num, cnt in df['number'].value_counts().head(10).items():
                    lines.append(f"  {num}  →  {cnt} records")
            if 'duration' in df.columns and 'number' in df.columns:
                lines += ["", "── Top 10 by Total Duration ────────────────"]
                for num, secs in df.groupby('number')['duration'].sum().nlargest(10).items():
                    lines.append(f"  {num}  →  {self.format_duration(secs)}")
            if 'hour' in df.columns:
                peak = df['hour'].value_counts().idxmax()
                lines += ["", f"Peak Activity Hour : {peak}:00"]

        if self.last_usage_report:
            vr = self.last_usage_report.get("voice_rows", [])
            sr = self.last_usage_report.get("sms_rows", [])
            lines += [
                "", "── PDF Statement Summary ───────────────────",
                f"  Voice calls : {len(vr)}",
                f"  SMS records : {len(sr)}",
                f"  Total voice duration: {self.format_duration(sum(r['seconds'] for r in vr))}",
            ]

        lines += ["", "═" * 55, "   END OF REPORT", "═" * 55]

        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", "\n".join(lines))
        self.report_text.configure(state="disabled")

    def export_report(self, fmt):
        content = self.report_text.get("1.0", "end").strip()
        if not content or content == "Load a CDR file to generate a report.":
            messagebox.showwarning("No Report", "Load a CDR file first.")
            return

        if fmt == "txt":
            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text File", "*.txt")],
                initialfile="CDR_Report.txt")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Exported", f"Report saved to:\n{path}")

        elif fmt == "pdf":
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF File", "*.pdf")],
                initialfile="CDR_Report.pdf")
            if path:
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Courier", size=9)
                    for line in content.split("\n"):
                        pdf.cell(0, 5, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
                    pdf.output(path)
                    messagebox.showinfo("Exported", f"PDF saved to:\n{path}")
                except Exception as e:
                    messagebox.showerror("Export Error", str(e))

    # ──────────────────────────────────────────────────────────
    # TOWER RESOLUTION
    # ──────────────────────────────────────────────────────────

    def resolve_locations(self, towers, token):
        resolved_count = 0
        total = len(towers)
        failed = []

        for i, tower in enumerate(towers):
            try:
                self.after(0, self.progress_bar.set, (i + 1) / total)
                url = "https://us1.unwiredlabs.com/v2/process.php"
                payload = {"token": token, "radio": "lte",
                           "mcc": tower['mcc'], "mnc": tower['mnc'],
                           "cells": [{"lac": tower['lac'], "cid": tower['cid']}],
                           "address": 1}
                resp = requests.post(url, json=payload, timeout=10)
                data = resp.json()

                if data.get('status') == 'ok':
                    lat, lon = data['lat'], data['lon']
                    address = data.get('address', 'Unknown')
                    self.after(0, self._add_marker, lat, lon, tower['cid'], address)
                    resolved_count += 1
                else:
                    failed.append(f"CID {tower['cid']}: {data.get('message','no location')}")
            except Exception as e:
                failed.append(f"CID {tower['cid']}: {e}")

        def _done():
            self.stats_label.configure(
                text=f"Towers: {total}  |  Mapped: {resolved_count}\n"
                     f"CDR Records: {len(self.cdr_df) if self.cdr_df is not None else 0}")
            if resolved_count > 0:
                self.map_widget.set_zoom(10)
            else:
                detail = "\n".join(failed[:5]) if failed else "No API details."
                messagebox.showwarning("Incomplete", f"No locations resolved.\n\n{detail}")
            self._set_status("Done.")

        self.after(0, _done)

    def _add_marker(self, lat, lon, cid, address):
        marker = self.map_widget.set_marker(lat, lon, text=f"CID: {cid}\n{address}")
        self.markers.append(marker)
        ctk.CTkLabel(self.list_frame, text=f"📍 {cid} — {address[:28]}",
                     font=("Arial", 11)).pack(pady=2, anchor="w")
        if len(self.markers) == 1:
            self.map_widget.set_position(lat, lon)

    # ──────────────────────────────────────────────────────────
    # ENV QUICK MAP
    # ──────────────────────────────────────────────────────────

    def quick_map_env(self):
        token = self.api_entry.get()
        if not token:
            messagebox.showwarning("Token Required", "Enter your Unwired Labs API token first.")
            return
        towers = self.extract_env_towers()
        if not towers:
            messagebox.showinfo("Missing Data",
                                "Add MY_MCC/MY_MNC/MY_LAC/MY_CID or TOWERS to your .env file.")
            return
        self._set_status("Mapping from .env…")
        threading.Thread(target=self.resolve_locations,
                         args=(towers, token), daemon=True).start()

    def extract_env_towers(self):
        towers = []
        raw = os.getenv("TOWERS", "").strip()
        if raw:
            for item in raw.split(";"):
                parts = [p.strip() for p in item.split(",")]
                if len(parts) == 4:
                    try:
                        towers.append({"mcc": int(parts[0]), "mnc": int(parts[1]),
                                       "lac": int(parts[2]), "cid": int(parts[3])})
                    except ValueError: pass
        for key, attr in [("MY_MCC","mcc"),("MY_MNC","mnc"),("MY_LAC","lac"),("MY_CID","cid")]:
            pass
        mcc, mnc, lac, cid = (os.getenv(k) for k in ["MY_MCC","MY_MNC","MY_LAC","MY_CID"])
        if all([mcc, mnc, lac, cid]):
            try:
                towers.append({"mcc": int(mcc), "mnc": int(mnc),
                               "lac": int(lac), "cid": int(cid)})
            except ValueError: pass
        unique = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique.values())

    # ──────────────────────────────────────────────────────────
    # CLEAR
    # ──────────────────────────────────────────────────────────

    def clear_all(self):
        for marker in self.markers:
            marker.delete()
        self.markers = []
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.cdr_df = None
        self.last_usage_report = None
        self.stats_label.configure(text="Towers: 0  |  Mapped: 0\nCDR Records: 0")
        self.progress_bar.set(0)
        self._set_status("Cleared.")

        self.insights_text.configure(state="normal")
        self.insights_text.delete("1.0", "end")
        self.insights_text.insert("1.0", "Load a PDF or CSV file to see CDR insights.\n")
        self.insights_text.configure(state="disabled")

        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", "Load a CDR file to generate a report.\n")
        self.report_text.configure(state="disabled")

        self.alerts_text.configure(state="normal")
        self.alerts_text.delete("1.0", "end")
        self.alerts_text.insert("1.0", "No alerts yet. Load a CDR file.\n")
        self.alerts_text.configure(state="disabled")

        for frm in [self.an_pie, self.an_bar, self.an_dur, self.an_hour,
                    self.tl_daily, self.tl_type, self.tl_dur, self.tl_contacts,
                    self.net_heat, self.net_graph]:
            for w in frm.winfo_children():
                w.destroy()
            ctk.CTkLabel(frm, text="Load a CDR file to populate.",
                         text_color="gray").pack(expand=True)


if __name__ == "__main__":
    app = CDRMapperApp()
    app.mainloop()
