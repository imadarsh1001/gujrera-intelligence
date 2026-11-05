import json
import threading
import urllib.request
from http.server import HTTPServer
from real_estate_intelligence.ui.server import IntelligenceRequestHandler

def test_endpoints():
    IntelligenceRequestHandler.setup_backends()
    srv = HTTPServer(('127.0.0.1', 8999), IntelligenceRequestHandler)
    t = threading.Thread(target=srv.serve_forever)
    t.daemon = True
    t.start()
    
    try:
        # 1. Projects endpoint
        r = urllib.request.urlopen('http://127.0.0.1:8999/api/projects')
        projects = json.loads(r.read())
        print(f"Verified /api/projects: {len(projects)} projects returned.")
        
        # 2. Graph endpoint
        r_graph = urllib.request.urlopen('http://127.0.0.1:8999/api/graph')
        graph_data = json.loads(r_graph.read())
        print(f"Verified /api/graph: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")
        
        # 3. Project detail
        r_p = urllib.request.urlopen('http://127.0.0.1:8999/api/project/13560')
        p_data = json.loads(r_p.read())
        p_name = p_data['project']['name']
        banks_count = len(p_data['banks'])
        form5_count = len(p_data['form5'])
        bu_count = len(p_data['bu_records'])
        print(f"Verified /api/project/13560: {p_name} | Banks: {banks_count} | Form 5: {form5_count} | BU records: {bu_count}")
        
        # 4. Search endpoint
        r_s = urllib.request.urlopen('http://127.0.0.1:8999/api/search?query=encumbrance&project_id=13560')
        s_data = json.loads(r_s.read())
        print(f"Verified /api/search: {len(s_data['results'])} hits found for 'encumbrance'.")

        # 5. Pricing endpoint
        r_pr = urllib.request.urlopen('http://127.0.0.1:8999/api/pricing/13560')
        pr_data = json.loads(r_pr.read())
        med_rate = pr_data['overall_rate_per_sqft'].get('median', 'N/A')
        print(f"Verified /api/pricing/13560: median rate = Rs {med_rate}/sq.ft across {pr_data['booked_units']} booked units.")

        # 6. Verify HTML index
        r_html = urllib.request.urlopen('http://127.0.0.1:8999/')
        html_len = len(r_html.read())
        print(f"Verified / (HTML index): {html_len} bytes served successfully.")

        print("\nALL UI SERVER ENDPOINTS FUNCTIONING FLAWLESSLY!")
    finally:
        srv.shutdown()

if __name__ == '__main__':
    test_endpoints()
