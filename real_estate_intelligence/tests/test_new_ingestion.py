import sqlite3
from pathlib import Path
from real_estate_intelligence.config import DEFAULT_SOURCE_RUN
from real_estate_intelligence.db.loader import ingest_from_run

TEST_DB = Path("data/test_intelligence.sqlite")

def main():
    if TEST_DB.exists():
        TEST_DB.unlink()
    print("Testing ingestion into:", TEST_DB)
    stats = ingest_from_run(DEFAULT_SOURCE_RUN, TEST_DB, index_documents=False)
    print("\nIngestion completed successfully!")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Inspect the newly loaded columns
    con = sqlite3.connect(TEST_DB)
    con.row_factory = sqlite3.Row
    prows = con.execute("SELECT project_id, name, tp_scheme, final_plot_no, survey_no, latitude, longitude, society_reg_date, bu_status, velocity_ratio, progress_status_label, has_complaints, has_alterations, default_quarters_count FROM projects").fetchall()
    print(f"\n--- Ingested {len(prows)} Projects with Quick Win Fields ---")
    for p in prows:
        print(f"Project {p['project_id']}: {p['name']}")
        print(f"  Land: TP={p['tp_scheme']}, FP={p['final_plot_no']}, Survey={p['survey_no']}, GPS=({p['latitude']}, {p['longitude']})")
        print(f"  Handover: SocietyReg={p['society_reg_date']}, BU={p['bu_status']}")
        print(f"  Velocity: Ratio={p['velocity_ratio']}, Status={p['progress_status_label']}")
        print(f"  Regulatory: Complaints={p['has_complaints']}, Alterations={p['has_alterations']}, Defaults={p['default_quarters_count']}")

    brows = con.execute("SELECT project_id, bank_name, account_type, account_name, account_number_masked, deposit_amt, withdrawal_amt, closing_bal FROM banks WHERE account_type = 1").fetchall()
    print(f"\n--- Ingested {len(brows)} Escrow 70% Bank Accounts ---")
    for b in brows:
        print(f"Project {b['project_id']}: Bank={b['bank_name']}, Account={b['account_number_masked']}, Deposit={b['deposit_amt']}, Withdrawal={b['withdrawal_amt']}, Closing={b['closing_bal']}")

    f5_cnt = con.execute("SELECT COUNT(*) FROM form5_compliance").fetchone()[0]
    noc_cnt = con.execute("SELECT COUNT(*) FROM noc_bu_records").fetchone()[0]
    print(f"\nForm 5 Compliance records: {f5_cnt}, NOC BU records: {noc_cnt}")

if __name__ == "__main__":
    main()
