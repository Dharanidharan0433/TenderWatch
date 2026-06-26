"""config.py — Global constants for TenderWatch."""
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tenderwatch.db")

COLOR_PRIMARY   = "#1E3A5F"
COLOR_SECONDARY = "#64748B"
COLOR_ACCENT    = "#F59E0B"
COLOR_SUCCESS   = "#16A34A"
COLOR_RISK      = "#DC2626"
COLOR_BG        = "#F8FAFC"
COLOR_BORDER    = "#CBD5E1"

RISK_THRESHOLDS = {
    "Low Risk":      (0, 0),
    "Moderate Risk": (1, 2),
    "High Risk":     (3, 4),
    "Critical Risk": (5, 5),
}

APP_TITLE = "TenderWatch"
APP_TAGLINE = "Government Procurement Risk Intelligence Platform"
