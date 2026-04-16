# 🛰️ CDR Intelligence Mapper & Visualization

A powerful and intuitive desktop application built with Python to parse Call Detail Records (CDR) statements, extract cell tower identifiers, and map locations interactively. Alongside mapping, the application features advanced intelligence insights to help analyze voice and SMS communication patterns, primarily designed to run seamlessly on telecommunication statements like Jio PDFs.

## 🌟 Key Features

*   **Cell Tower Geolocation:** Extracts Mobile Country Code (`MCC`), Mobile Network Code (`MNC`), Location Area Code (`LAC`), and CellID (`CID`) variables using `pandas` and `pdfplumber`. Resolves the precise GPS coordinates utilizing the incredible [Unwired Labs API](https://unwiredlabs.com/) and maps them on an interactive `TkinterMapView`.
*   **CDR Insights & Analytics:** Automatically processes Jio (or similar) uncompressed PDF billing statements to outline granular insights:
    *   Total call duration, unique numbers interacted with, and top longest calls.
    *   Daily timeline metrics (calls and SMS count per day).
    *   "Most Called Numbers" metrics.
*   **Multi-Format Upload:** Built-in heuristics extract tower parameters directly from tabular structures or unstructured texts natively in **PDFs** or **CSV** logs.
*   **Quick Map by Environment:** Debug or immediately lookup towers dynamically via environment variable overrides (`.env`) for `TOWERS` or `MY_MCC`, `MY_MNC`, etc., bypassing file loads.
*   **Modern UI:** Developed relying on `CustomTkinter` offering an elegant Dark Mode responsive dashboard.

## 📸 Overview

The application features a modern tabbed layout:
- **Map View:** Visual tracker pinpointing coordinates with respective physical location addresses and CID hover actions.
- **Insights View:** Detailed generated textual report summarizing your telecom log metrics seamlessly decoded from the parsed document.

## 🛠️ Installation & Setup

1. **Clone the Repository:**
    ```bash
    git clone https://github.com/Stavin13/CDR-mapper.git
    cd CDR-mapper
    ```

2. **Set up a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On macOS/Linux
    # venv\Scripts\activate   # On Windows
    ```

3. **Install Requirements:**
    ```bash
    pip install -r requirements.txt
    ```

    Ensure your environment contains the dependencies mapping to:
    `customtkinter`, `tkintermapview`, `pdfplumber`, `pandas`, `requests`, `python-dotenv`

4. **Environment Configuration:**
    Create a `.env` file in the root directory. You will need a free API token from [Unwired Labs](https://unwiredlabs.com/).
    ```env
    UNWIRED_TOKEN=your_api_token_here

    # Optional: Quick map testing variables
    MY_MCC=404
    MY_MNC=20
    MY_LAC=1020
    MY_CID=14012
    # Alternate towers string format (MCC,MNC,LAC,CID;...)
    # TOWERS=404,20,1020,14012;404,20,1020,14015
    ```

## 🚀 Usage

Execute the program:
```bash
python3 cdr_mapper.py
```

*   **Load PDF/CSV:** Click `Load PDF / CSV` and select a compatible file. Wait for the mapping resolution progression.
*   **Insights:** Change tabs sequentially from `Map` -> `Insights` to view your parsed communication logs statistics.
*   **Quick Test:** Press `Map Towers from .env` to execute API requests with your configured placeholder variables in `.env`.

## 🛡️ License

Please review the standard `LICENSE` distributed over this repository for usage capabilities and permissions.
