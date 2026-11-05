import sqlite3
import sys
from pathlib import Path
import unittest

from real_estate_intelligence.analytics.investor_dossier import generate_investor_dossier

class TestDossierGen(unittest.TestCase):
    def test_dossier_output(self):
        db_path = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
        if not db_path.exists():
            self.skipTest(f"Database {db_path} not found")
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        try:
            for pid in [13560, 17830]:
                dossier = generate_investor_dossier(con, pid)
                self.assertIn("Institutional Due-Diligence Dossier", dossier)
                self.assertIn("Executive 4-Quadrant Analysis", dossier)
        finally:
            con.close()

if __name__ == "__main__":
    unittest.main()
