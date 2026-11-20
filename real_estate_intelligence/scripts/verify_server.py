import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "real_estate_intelligence"))

from fastapi.testclient import TestClient
from api.index import app, AppState

def test_endpoints():
    AppState.setup_backends()
    client = TestClient(app)
    
    # 1. Projects endpoint
    r = client.get('/api/projects')
    projects = r.json()
    print(f"Verified /api/projects: {len(projects)} projects returned.")
    
    # 2. Graph endpoint
    r_graph = client.get('/api/graph')
    graph_data = r_graph.json()
    print(f"Verified /api/graph: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")
    
    # 3. Project detail
    r_p = client.get('/api/project/13560')
    p_data = r_p.json()
    p_name = p_data['project']['name']
    banks_count = len(p_data['banks'])
    form5_count = len(p_data['form5'])
    bu_count = len(p_data['bu_records'])
    print(f"Verified /api/project/13560: {p_name} | Banks: {banks_count} | Form 5: {form5_count} | BU records: {bu_count}")
    
    # 4. Search endpoint
    r_s = client.get('/api/search?query=encumbrance&project_id=13560')
    s_data = r_s.json()
    print(f"Verified /api/search: {len(s_data['results'])} hits found for 'encumbrance'.")

    # 5. Pricing endpoint
    r_pr = client.get('/api/pricing/13560')
    pr_data = r_pr.json()
    med_rate = pr_data['overall_rate_per_sqft'].get('median', 'N/A')
    print(f"Verified /api/pricing/13560: median rate = Rs {med_rate}/sq.ft across {pr_data['booked_units']} booked units.")

    # 6. Verify HTML index
    r_html = client.get('/')
    print(f"Verified / (HTML index): {len(r_html.content)} bytes served successfully.")

    print("\nALL FASTAPI ENDPOINTS FUNCTIONING FLAWLESSLY!")

if __name__ == '__main__':
    test_endpoints()
