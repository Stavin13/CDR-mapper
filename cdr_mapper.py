import os
import re
import requests
import pdfplumber
import customtkinter as ctk
from collections import Counter, defaultdict
from tkintermapview import TkinterMapView
from tkinter import filedialog, messagebox
import pandas as pd
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Appearance and Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CDRMapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CDR Intelligence Mapper & Visualization")
        self.geometry("1400x900")

        # Data structure for markers
        self.markers = []
        self.results_data = []
        self.last_usage_report = None

        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        row_idx = 0
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="🛰️ CDR MAPPER v1", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=row_idx, column=0, padx=20, pady=(20, 10))
        row_idx += 1

        # API Key Input
        self.api_label = ctk.CTkLabel(self.sidebar_frame, text="Unwired Labs API Token:", font=ctk.CTkFont(size=14))
        self.api_label.grid(row=row_idx, column=0, padx=20, pady=(10, 0), sticky="w")
        row_idx += 1
        
        env_token = os.getenv("UNWIRED_TOKEN", "")
        self.api_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Enter API Token Key", show="*")
        self.api_entry.grid(row=row_idx, column=0, padx=20, pady=(5, 10), sticky="ew")
        if env_token:
            self.api_entry.insert(0, env_token)
        row_idx += 1

        # Load File Button
        self.upload_btn = ctk.CTkButton(self.sidebar_frame, text="Load PDF / CSV", command=self.load_file, height=45)
        self.upload_btn.grid(row=row_idx, column=0, padx=20, pady=20, sticky="ew")
        row_idx += 1

        # Statistics Label
        self.stats_label = ctk.CTkLabel(self.sidebar_frame, text="Extracted: 0 Towers\nMapped: 0 Points", justify="left")
        self.stats_label.grid(row=row_idx, column=0, padx=20, pady=10, sticky="w")
        row_idx += 1

        # Quick Map from ENV Button
        self.quick_btn = ctk.CTkButton(self.sidebar_frame, text="Map Towers from .env", command=self.quick_map_env, fg_color="#2ecc71", hover_color="#27ae60")
        self.quick_btn.grid(row=row_idx, column=0, padx=20, pady=10, sticky="ew")
        row_idx += 1

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.sidebar_frame, orientation="horizontal")
        self.progress_bar.grid(row=row_idx, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.set(0)
        row_idx += 1

        # Clear Map Button
        self.clear_btn = ctk.CTkButton(self.sidebar_frame, text="🗑️ Clear Map", command=self.clear_all, fg_color="transparent", border_width=2)
        self.clear_btn.grid(row=row_idx, column=0, padx=20, pady=20, sticky="ew")
        row_idx += 1

        # List View
        self.list_frame = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Detected Tower Info", height=300)
        self.list_frame.grid(row=row_idx, column=0, padx=20, pady=10, sticky="nsew")

        # Main Tab View
        self.tab_view = ctk.CTkTabview(self, corner_radius=8)
        self.tab_view.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")
        self.tab_view.add("Map")
        self.tab_view.add("Insights")

        # Main Map View
        self.map_frame = self.tab_view.tab("Map")
        self.map_frame.grid_rowconfigure(0, weight=1)
        self.map_frame.grid_columnconfigure(0, weight=1)

        self.map_widget = TkinterMapView(self.map_frame, corner_radius=10)
        self.map_widget.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.map_widget.set_position(20.5937, 78.9629) # Center of India (example)
        self.map_widget.set_zoom(5)

        # Usage Insights View
        self.insights_frame = self.tab_view.tab("Insights")
        self.insights_frame.grid_rowconfigure(1, weight=1)
        self.insights_frame.grid_columnconfigure(0, weight=1)
        self.insights_title = ctk.CTkLabel(
            self.insights_frame,
            text="Load a Jio statement PDF to see call and SMS insights.",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.insights_title.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        self.insights_text = ctk.CTkTextbox(self.insights_frame, wrap="word")
        self.insights_text.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.insights_text.insert("1.0", "No usage analysis yet.\n")
        self.insights_text.configure(state="disabled")

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CDR Files", "*.pdf *.csv"), ("PDF", "*.pdf"), ("CSV", "*.csv")])
        if not file_path:
            return
            
        token = self.api_entry.get()
        if not token:
            messagebox.showwarning("API Token Required", "Please enter your Unwired Labs API token first.")
            return

        self.progress_bar.set(0)
        self.results_data = []
        
        try:
            usage_report = None
            if file_path.lower().endswith('.pdf'):
                towers = self.extract_pdf_data(file_path)
                usage_report = self.extract_usage_data(file_path)
            elif file_path.lower().endswith('.csv'):
                towers = self.extract_csv_data(file_path)
            else:
                messagebox.showerror("Unsupported", "Only PDF and CSV files are supported.")
                return

            if usage_report:
                self.display_usage_report(usage_report)
                self.tab_view.set("Insights")

            if towers:
                self.stats_label.configure(text=f"Extracted: {len(towers)} Towers\nMapping...")
                self.resolve_locations(towers, token)
            elif not usage_report:
                messagebox.showinfo("No Data", "Could not find tower identifiers or usage records in the file.")
            else:
                self.stats_label.configure(text="Extracted: 0 Towers\nUsage analyzed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process file: {str(e)}")

    def extract_csv_data(self, file_path):
        towers = []
        try:
            df = pd.read_csv(file_path)
            # Find columns
            cols = [str(c).lower() for c in df.columns]
            mcc_idx = mnc_idx = lac_idx = cid_idx = -1
            
            for i, col in enumerate(cols):
                if 'mcc' in col: mcc_idx = i
                elif 'mnc' in col: mnc_idx = i
                elif 'lac' in col or 'tac' in col: lac_idx = i
                elif 'cid' in col or 'cellid' in col or 'cell' in col: cid_idx = i
            
            if mcc_idx != -1 and mnc_idx != -1 and lac_idx != -1 and cid_idx != -1:
                # Direct extraction from columns
                for _, row in df.iterrows():
                    try:
                        towers.append({
                            'mcc': int(str(row.iloc[mcc_idx]).strip()),
                            'mnc': int(str(row.iloc[mnc_idx]).strip()),
                            'lac': int(str(row.iloc[lac_idx]).strip()),
                            'cid': int(str(row.iloc[cid_idx]).strip())
                        })
                    except: pass
            else:
                # Fallback: scan everywhere in the CSV for identifiers (unstructured)
                text = df.to_string()
                regex = r'(MCC[:\s-]*)?(\d{3})[,\s-]+(MNC[:\s-]*)?(\d{2,3})[,\s-]+(LAC[:\s-]*)?(\d{2,5})[,\s-]+(CID[:\s-]*)?(\d{2,10})'
                matches = re.finditer(regex, text, re.IGNORECASE)
                for m in matches:
                    towers.append({
                        'mcc': int(m.group(2)),
                        'mnc': int(m.group(4)),
                        'lac': int(m.group(6)),
                        'cid': int(m.group(8))
                    })
        except Exception as e:
            print(f"CSV Parse Error: {e}")
            
        unique_towers = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique_towers.values())

    def extract_usage_data(self, file_path):
        voice_rows = []
        sms_rows = []
        mode = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    clean_line = line.strip()
                    if "2.0 Voice" in clean_line:
                        mode = "voice"
                        continue
                    if "3.0 SMS" in clean_line:
                        mode = "sms"
                        continue
                    if re.search(r"^\s*(Subtotal|Usage in India Total|Voice Total|SMS Total|Page)\b", clean_line):
                        continue

                    row_match = re.match(
                        r"^\s*\d+\s+(\d{2}-[A-Z]{3}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+((?:\+?91)?[6-9]\d{9})\s+(.+)$",
                        clean_line
                    )
                    if not row_match:
                        continue

                    values = row_match.group(4).split()
                    if mode == "voice" and len(values) >= 5:
                        try:
                            voice_rows.append({
                                "date": row_match.group(1),
                                "time": row_match.group(2),
                                "number": self.normalize_phone(row_match.group(3)),
                                "seconds": int(values[0]),
                            })
                        except ValueError:
                            continue
                    elif mode == "sms" and len(values) >= 4:
                        try:
                            sms_rows.append({
                                "date": row_match.group(1),
                                "time": row_match.group(2),
                                "number": self.normalize_phone(row_match.group(3)),
                                "count": int(values[0]),
                            })
                        except ValueError:
                            continue

        if not voice_rows and not sms_rows:
            return None

        return {
            "voice_rows": voice_rows,
            "sms_rows": sms_rows,
        }

    def normalize_phone(self, number):
        digits = re.sub(r"\D", "", number)
        if len(digits) == 10:
            return f"91{digits}"
        return digits

    def format_duration(self, seconds):
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def display_usage_report(self, report):
        self.last_usage_report = report
        voice_rows = report["voice_rows"]
        sms_rows = report["sms_rows"]

        call_counts = Counter(row["number"] for row in voice_rows)
        duration_by_number = defaultdict(int)
        calls_by_day = Counter()
        for row in voice_rows:
            duration_by_number[row["number"]] += row["seconds"]
            calls_by_day[row["date"]] += 1

        sms_counts = Counter()
        sms_by_day = Counter()
        for row in sms_rows:
            sms_counts[row["number"]] += row["count"]
            sms_by_day[row["date"]] += row["count"]

        total_call_seconds = sum(row["seconds"] for row in voice_rows)
        longest_calls = sorted(voice_rows, key=lambda row: row["seconds"], reverse=True)[:10]

        lines = [
            "CDR Usage Insights",
            "",
            f"Voice calls: {len(voice_rows)}",
            f"Unique voice numbers: {len(call_counts)}",
            f"Total call duration: {self.format_duration(total_call_seconds)}",
            f"SMS records: {len(sms_rows)}",
            f"Total SMS count: {sum(row['count'] for row in sms_rows)}",
            f"Unique SMS numbers: {len(sms_counts)}",
            "",
            "Most Called Numbers",
        ]

        if call_counts:
            for number, count in call_counts.most_common(10):
                lines.append(f"{number}: {count} calls")
        else:
            lines.append("No voice calls found.")

        lines.extend(["", "Highest Total Call Duration"])
        if duration_by_number:
            for number, seconds in sorted(duration_by_number.items(), key=lambda item: item[1], reverse=True)[:10]:
                lines.append(f"{number}: {self.format_duration(seconds)}")
        else:
            lines.append("No voice duration found.")

        lines.extend(["", "Longest Individual Calls"])
        if longest_calls:
            for row in longest_calls:
                lines.append(f"{row['date']} {row['time']} | {row['number']} | {self.format_duration(row['seconds'])}")
        else:
            lines.append("No voice calls found.")

        lines.extend(["", "SMS Info"])
        if sms_rows:
            for number, count in sms_counts.most_common(10):
                lines.append(f"{number}: {count} SMS")
            lines.append("")
            lines.append("SMS Records")
            for row in sms_rows[:25]:
                lines.append(f"{row['date']} {row['time']} | {row['number']} | {row['count']} SMS")
        else:
            lines.append("No SMS found.")

        lines.extend(["", "Calls By Day"])
        if calls_by_day:
            for day, count in sorted(calls_by_day.items()):
                lines.append(f"{day}: {count} calls")
        else:
            lines.append("No daily voice data found.")

        if sms_by_day:
            lines.extend(["", "SMS By Day"])
            for day, count in sorted(sms_by_day.items()):
                lines.append(f"{day}: {count} SMS")

        self.insights_text.configure(state="normal")
        self.insights_text.delete("1.0", "end")
        self.insights_text.insert("1.0", "\n".join(lines))
        self.insights_text.configure(state="disabled")

    def extract_pdf_data(self, file_path):
        towers = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # 1. Search for tables
                tables = page.extract_tables()
                for table in tables:
                    df = pd.DataFrame(table)
                    mcc_idx, mnc_idx, lac_idx, cid_idx = -1, -1, -1, -1
                    if not df.empty:
                        first_row = [str(x).lower() for x in df.iloc[0]]
                        for i, cell in enumerate(first_row):
                            if 'mcc' in cell: mcc_idx = i
                            elif 'mnc' in cell: mnc_idx = i
                            elif 'lac' in cell or 'tac' in cell: lac_idx = i
                            elif 'cid' in cell or 'cellid' in cell or 'cell' in cell: cid_idx = i
                        
                        if mcc_idx != -1 and mnc_idx != -1 and lac_idx != -1 and cid_idx != -1:
                            for idx, row in df.iterrows():
                                if idx == 0: continue
                                try:
                                    towers.append({
                                        'mcc': int(str(row[mcc_idx]).strip()),
                                        'mnc': int(str(row[mnc_idx]).strip()),
                                        'lac': int(str(row[lac_idx]).strip()),
                                        'cid': int(str(row[cid_idx]).strip())
                                    })
                                except: pass

                # 2. Text-based Regex
                text = page.extract_text() or ""
                regex = r'(MCC[:\s-]*)?(\d{3})[,\s-]+(MNC[:\s-]*)?(\d{2,3})[,\s-]+(LAC[:\s-]*)?(\d{2,5})[,\s-]+(CID[:\s-]*)?(\d{2,10})'
                matches = re.finditer(regex, text, re.IGNORECASE)
                for m in matches:
                    towers.append({
                        'mcc': int(m.group(2)),
                        'mnc': int(m.group(4)),
                        'lac': int(m.group(6)),
                        'cid': int(m.group(8))
                    })

        unique_towers = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique_towers.values())

    def resolve_locations(self, towers, token):
        self.progress_bar.set(0)
        resolved_count = 0
        total = len(towers)
        failed_responses = []
        
        for i, tower in enumerate(towers):
            try:
                self.progress_bar.set((i + 1) / total)
                self.update_idletasks()

                url = "https://us1.unwiredlabs.com/v2/process.php"
                payload = {
                    "token": token,
                    "radio": "lte",
                    "mcc": tower['mcc'],
                    "mnc": tower['mnc'],
                    "cells": [{"lac": tower['lac'], "cid": tower['cid']}],
                    "address": 1
                }
                
                resp = requests.post(url, json=payload, timeout=10)
                data = resp.json()

                if data.get('status') == 'ok':
                    lat, lon = data['lat'], data['lon']
                    address = data.get('address', 'Unknown Location')
                    
                    marker = self.map_widget.set_marker(lat, lon, text=f"CID: {tower['cid']}\n{address}")
                    self.markers.append(marker)
                    
                    ctk.CTkLabel(self.list_frame, text=f"📍 {tower['cid']} - {address[:30]}...", font=("Arial", 11)).pack(pady=2, anchor="w")
                    
                    if resolved_count == 0:
                        self.map_widget.set_position(lat, lon)
                    
                    resolved_count += 1
                else:
                    failed_responses.append(
                        f"CID {tower['cid']}: {data.get('message') or data.get('status') or 'No location found'}"
                    )

            except Exception as e:
                failed_responses.append(f"CID {tower['cid']}: {e}")
                print(f"Error resolving {tower['cid']}: {e}")

        self.stats_label.configure(text=f"Extracted: {total} Towers\nMapped: {resolved_count} Points")
        if resolved_count > 0:
            self.map_widget.set_zoom(10)
        else:
            detail = "\n".join(failed_responses[:5]) if failed_responses else "No API details returned."
            messagebox.showwarning("Incomplete", f"No locations resolved.\n\n{detail}")

    def quick_map_env(self):
        token = self.api_entry.get()
        if not token:
            messagebox.showwarning("API Token Required", "Please enter your Unwired Labs API token first.")
            return

        towers = self.extract_env_towers()
        if not towers:
            messagebox.showinfo(
                "Missing Data",
                "Add MY_MCC/MY_MNC/MY_LAC/MY_CID or TOWERS to your .env file."
            )
            return

        self.stats_label.configure(text=f"Extracted: {len(towers)} Towers\nMapping from .env...")
        self.resolve_locations(towers, token)

    def extract_env_towers(self):
        towers = []
        towers_raw = os.getenv("TOWERS", "").strip()
        if towers_raw:
            for item in towers_raw.split(";"):
                parts = [part.strip() for part in item.split(",")]
                if len(parts) != 4:
                    continue
                try:
                    towers.append({
                        "mcc": int(parts[0]),
                        "mnc": int(parts[1]),
                        "lac": int(parts[2]),
                        "cid": int(parts[3]),
                    })
                except ValueError:
                    continue

        mcc = os.getenv("MY_MCC")
        mnc = os.getenv("MY_MNC")
        lac = os.getenv("MY_LAC")
        cid = os.getenv("MY_CID")

        if all([mcc, mnc, lac, cid]):
            try:
                towers.append({"mcc": int(mcc), "mnc": int(mnc), "lac": int(lac), "cid": int(cid)})
            except ValueError:
                pass

        unique_towers = {f"{t['mcc']}-{t['mnc']}-{t['lac']}-{t['cid']}": t for t in towers}
        return list(unique_towers.values())

    def clear_all(self):
        for marker in self.markers:
            marker.delete()
        self.markers = []
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.stats_label.configure(text="Extracted: 0 Towers\nMapped: 0 Points")
        self.progress_bar.set(0)
        self.insights_text.configure(state="normal")
        self.insights_text.delete("1.0", "end")
        self.insights_text.insert("1.0", "No usage analysis yet.\n")
        self.insights_text.configure(state="disabled")

if __name__ == "__main__":
    app = CDRMapperApp()
    app.mainloop()
