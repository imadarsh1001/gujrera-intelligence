/**
 * GujRERA Real Estate Intelligence Platform - Statewide Insights Radar
 * 
 * Provides:
 * 1. Zombie Projects Radar (Modern private schemes past deadline with no registered BU/NOC)
 * 2. Statewide Asking Price Markup & Micro-Market Spread (idx_unit_status_rates covering aggregate)
 * 3. Developer Portfolio & Brand Cluster Resolution (Composite Key (c) partitioning)
 */

let _insightsInitialized = false;

async function initInsightsTab() {
    if (_insightsInitialized) return;
    _insightsInitialized = true;
    await Promise.all([
        renderZombieRadar(),
        renderMarkupSpread(),
        renderDeveloperClusters()
    ]);
}

// 1. ZOMBIE PROJECTS RADAR
async function renderZombieRadar() {
    const container = document.getElementById('insightsZombieContainer');
    if (!container) return;
    container.innerHTML = '<div class="p-6 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading Zombie Projects Radar...</div>';

    try {
        const resp = await fetch('/api/insights/zombie_radar?limit=50');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const projects = await resp.json();

        if (!projects || projects.length === 0) {
            container.innerHTML = '<div class="p-6 text-slate-500 text-sm">No expired schemes without BU found matching criteria.</div>';
            return;
        }

        let html = `
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-600">
                    <thead class="bg-slate-50 border-b border-slate-200 text-slate-700 uppercase font-semibold text-[11px]">
                        <tr>
                            <th class="py-2.5 px-3">Project & Promoter</th>
                            <th class="py-2.5 px-3">District</th>
                            <th class="py-2.5 px-3">Completion Due</th>
                            <th class="py-2.5 px-3">Overdue Status</th>
                            <th class="py-2.5 px-3 text-right">Trapped Units</th>
                            <th class="py-2.5 px-3 text-right">Absorption</th>
                            <th class="py-2.5 px-3 text-right">Min Rate</th>
                            <th class="py-2.5 px-3 text-center">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
        `;

        projects.forEach(p => {
            const booked = (p.booked_units || 0).toLocaleString();
            const total = (p.total_units || 0).toLocaleString();
            const abs = p.absorption_pct != null ? `${p.absorption_pct}%` : 'N/A';
            const rate = p.min_rate_sqft_booked ? `₹${Math.round(p.min_rate_sqft_booked).toLocaleString()}` : '-';
            const badge = p.status_badge || `🔴 EXPIRED_WITHOUT_BU (+${p.months_overdue || 0}m)`;

            html += `
                <tr class="hover:bg-slate-50 transition-colors">
                    <td class="py-2.5 px-3">
                        <div class="font-medium text-slate-900">${esc(p.name || 'Unnamed')}</div>
                        <div class="text-[11px] text-slate-400 truncate max-w-xs">${esc(p.promoter_name || 'Unknown')}</div>
                    </td>
                    <td class="py-2.5 px-3 whitespace-nowrap">${esc(p.district || '-')}</td>
                    <td class="py-2.5 px-3 whitespace-nowrap font-mono text-slate-500">${esc(p.completion_date || '-')}</td>
                    <td class="py-2.5 px-3 whitespace-nowrap">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            ${esc(badge)}
                        </span>
                    </td>
                    <td class="py-2.5 px-3 text-right whitespace-nowrap font-semibold text-rose-600">${booked} <span class="font-normal text-slate-400">/ ${total}</span></td>
                    <td class="py-2.5 px-3 text-right whitespace-nowrap">${abs}</td>
                    <td class="py-2.5 px-3 text-right whitespace-nowrap font-mono">${rate}</td>
                    <td class="py-2.5 px-3 text-center whitespace-nowrap">
                        <button onclick="openProjectDetail(${p.project_id})" class="px-2 py-1 text-[11px] font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded transition-colors">
                            View Dossier →
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<div class="p-6 text-rose-600 text-sm">Failed to load Zombie Projects: ${esc(err.message)}</div>`;
    }
}

// 2. STATEWIDE ASKING PRICE MARKUP & SPREAD
async function renderMarkupSpread() {
    const container = document.getElementById('insightsMarkupContainer');
    if (!container) return;
    container.innerHTML = '<div class="p-6 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading Markup Spread...</div>';

    try {
        const resp = await fetch('/api/insights/markup_spread');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        const baseline = data.statewide_baseline_markup_pct || 12.63;
        const empirical = data.empirical_markup_pct || 12.48;
        const txSummary = data.statewide_transactions_summary || {};
        const booked = txSummary.BOOKED || {};
        const unbooked = txSummary.UNBOOKED || {};

        const bookedCnt = (booked.unit_count || 0).toLocaleString();
        const bookedAvg = booked.avg_rate_per_sqft ? `₹${Math.round(booked.avg_rate_per_sqft).toLocaleString()}/sq.ft.` : '-';
        const unbookedCnt = (unbooked.unit_count || 0).toLocaleString();
        const unbookedAvg = unbooked.avg_rate_per_sqft ? `₹${Math.round(unbooked.avg_rate_per_sqft).toLocaleString()}/sq.ft.` : '-';

        let html = `
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-blue-50 border border-blue-100 rounded-lg p-4">
                    <div class="text-[11px] font-semibold uppercase text-blue-700 tracking-wider">Statutory Baseline Markup</div>
                    <div class="text-2xl font-bold text-blue-900 mt-1">+${baseline}%</div>
                    <div class="text-xs text-blue-600 mt-1">Sovereign reference rate</div>
                </div>
                <div class="bg-indigo-50 border border-indigo-100 rounded-lg p-4">
                    <div class="text-[11px] font-semibold uppercase text-indigo-700 tracking-wider">Empirical Portal Markup</div>
                    <div class="text-2xl font-bold text-indigo-900 mt-1">+${empirical}%</div>
                    <div class="text-xs text-indigo-600 mt-1">Asking rate vs. registered consideration</div>
                </div>
                <div class="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <div class="text-[11px] font-semibold uppercase text-slate-500 tracking-wider">Booked Registered Deeds</div>
                    <div class="text-xl font-bold text-slate-900 mt-1">${bookedCnt}</div>
                    <div class="text-xs text-slate-500 mt-1">Avg rate: <span class="font-semibold text-slate-700">${bookedAvg}</span></div>
                </div>
                <div class="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <div class="text-[11px] font-semibold uppercase text-slate-500 tracking-wider">Unbooked Asking Units</div>
                    <div class="text-xl font-bold text-slate-900 mt-1">${unbookedCnt}</div>
                    <div class="text-xs text-slate-500 mt-1">Avg asking: <span class="font-semibold text-slate-700">${unbookedAvg}</span></div>
                </div>
            </div>

            <div class="font-semibold text-sm text-slate-800 mb-2">Top 10 Districts Absorption & Registered Rates</div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-600">
                    <thead class="bg-slate-50 border-b border-slate-200 text-slate-700 uppercase font-semibold text-[11px]">
                        <tr>
                            <th class="py-2 px-3">District</th>
                            <th class="py-2 px-3 text-right">Projects</th>
                            <th class="py-2 px-3 text-right">Booked Units</th>
                            <th class="py-2 px-3 text-right">Unbooked Units</th>
                            <th class="py-2 px-3 text-right">Absorption Rate</th>
                            <th class="py-2 px-3 text-right">Avg Min Rate</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
        `;

        (data.top_districts_breakdown || []).forEach(d => {
            const b = d.total_booked_units || 0;
            const u = d.total_unbooked_units || 0;
            const tot = b + u;
            const absPct = tot > 0 ? `${((b / tot) * 100).toFixed(1)}%` : '-';
            const rate = d.avg_min_rate_sqft_booked ? `₹${Math.round(d.avg_min_rate_sqft_booked).toLocaleString()}` : '-';

            html += `
                <tr class="hover:bg-slate-50 transition-colors">
                    <td class="py-2 px-3 font-medium text-slate-900">${esc(d.district)}</td>
                    <td class="py-2 px-3 text-right font-mono">${(d.project_count || 0).toLocaleString()}</td>
                    <td class="py-2 px-3 text-right font-mono text-emerald-700 font-semibold">${b.toLocaleString()}</td>
                    <td class="py-2 px-3 text-right font-mono text-slate-500">${u.toLocaleString()}</td>
                    <td class="py-2 px-3 text-right font-semibold text-slate-700">${absPct}</td>
                    <td class="py-2 px-3 text-right font-mono">${rate}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
            <div class="mt-2 text-[11px] text-slate-400">
                Index backing: <code class="bg-slate-100 px-1 py-0.5 rounded text-slate-600">idx_unit_status_rates</code> on 1.95M unit deeds.
            </div>
        `;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<div class="p-6 text-rose-600 text-sm">Failed to load Markup Spread: ${esc(err.message)}</div>`;
    }
}

// 3. DEVELOPER PORTFOLIO & BRAND CLUSTER RESOLUTION
async function renderDeveloperClusters(promoterName = null) {
    const container = document.getElementById('insightsClustersContainer');
    if (!container) return;
    container.innerHTML = '<div class="p-6 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Resolving Developer Clusters...</div>';

    try {
        const url = promoterName && promoterName.trim()
            ? `/api/insights/developer_clusters?promoter_name=${encodeURIComponent(promoterName.trim())}`
            : '/api/insights/developer_clusters';
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (data.mode === 'statewide_developer_overview') {
            let html = `
                <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-xs text-amber-900">
                    <div class="font-bold mb-1"><i class="fa-solid fa-circle-info mr-1"></i>Composite Key (c) Cluster Resolution</div>
                    Common promoter brand names across Gujarat (e.g. <em>SHREEJI</em>, <em>SHALIGRAM</em>) often represent legally distinct partnerships in different cities.
                    Querying a brand partitions projects into disjoint clusters based on shared Council of Architecture licenses and bank branch IFSC anchors.
                </div>
                <div class="font-semibold text-sm text-slate-800 mb-2">Most Frequent Promoter Brands in Gujarat</div>
                <div class="flex flex-wrap gap-2 mb-4">
            `;

            (data.frequent_brand_names || []).forEach(brand => {
                html += `
                    <button onclick="searchDeveloperCluster('${esc(brand)}')" class="px-3 py-1.5 text-xs font-medium rounded-full bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition-colors">
                        <i class="fa-solid fa-magnifying-glass text-[10px] mr-1 text-slate-400"></i>${esc(brand)}
                    </button>
                `;
            });

            html += `
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-600">
                        <thead class="bg-slate-50 border-b border-slate-200 text-slate-700 uppercase font-semibold text-[11px]">
                            <tr>
                                <th class="py-2 px-3">Promoter Name</th>
                                <th class="py-2 px-3 text-right">Total Projects</th>
                                <th class="py-2 px-3 text-center">Cluster Analysis</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
            `;

            (data.top_promoters_by_project_count || []).forEach(p => {
                html += `
                    <tr class="hover:bg-slate-50 transition-colors">
                        <td class="py-2 px-3 font-medium text-slate-900">${esc(p.promoter_name)}</td>
                        <td class="py-2 px-3 text-right font-mono">${p.project_count}</td>
                        <td class="py-2 px-3 text-center">
                            <button onclick="searchDeveloperCluster('${esc(p.promoter_name)}')" class="px-2 py-0.5 text-[11px] font-medium text-blue-600 hover:underline">
                                Partition Clusters →
                            </button>
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
            return;
        }

        // Targeted Cluster Results
        const clusters = data.clusters || [];
        const topConfidence = data.linkage_confidence || 'MEDIUM';
        const confColor = topConfidence === 'PARTITIONED_MULTI_CLUSTER' 
            ? 'bg-amber-100 text-amber-800 border-amber-300'
            : topConfidence === 'HIGH'
            ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
            : 'bg-slate-100 text-slate-700 border-slate-300';

        let html = `
            <div class="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg p-3.5 mb-4">
                <div>
                    <span class="text-xs text-slate-500 uppercase tracking-wider font-semibold">Promoter Query:</span>
                    <span class="ml-2 font-bold text-slate-900">${esc(data.promoter_name || promoterName)}</span>
                    <span class="ml-3 text-xs text-slate-500">(${data.portfolio_count || 0} total projects in ${clusters.length} disjoint cluster${clusters.length === 1 ? '' : 's'})</span>
                </div>
                <span class="px-2.5 py-1 rounded text-xs font-bold border ${confColor}">
                    ${esc(topConfidence)}
                </span>
            </div>
        `;

        if (clusters.length === 0) {
            html += '<div class="p-6 text-slate-500 text-sm">No project clusters found for this promoter name.</div>';
        } else {
            clusters.forEach(cl => {
                const districts = (cl.districts || []).join(', ');
                const lics = (cl.shared_anchors && cl.shared_anchors.shared_licenses) || [];
                const banks = (cl.shared_anchors && cl.shared_anchors.shared_banks) || [];
                const expiredCount = cl.modern_expired_no_bu_count || 0;

                const clConfColor = cl.linkage_confidence === 'HIGH'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : cl.linkage_confidence === 'MEDIUM'
                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200';

                html += `
                    <div class="border border-slate-200 rounded-lg p-4 mb-4 bg-white shadow-sm">
                        <div class="flex flex-wrap items-center justify-between pb-3 border-b border-slate-100 gap-2">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-800 text-sm">Cluster #${cl.cluster_id}: ${esc(districts)}</span>
                                <span class="px-2 py-0.5 rounded text-[11px] font-semibold border ${clConfColor}">${esc(cl.linkage_confidence)}</span>
                                <span class="text-xs text-slate-400">· ${cl.portfolio_count} project${cl.portfolio_count === 1 ? '' : 's'}</span>
                            </div>
                            ${expiredCount > 0 ? `
                                <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                    🔴 ${expiredCount} expired without BU
                                </span>
                            ` : `
                                <span class="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    ✅ 0 expired without BU
                                </span>
                            `}
                        </div>

                        <!-- Anchors -->
                        <div class="py-2.5 text-xs text-slate-600 flex flex-wrap gap-4 border-b border-slate-100">
                            <div>
                                <span class="font-semibold text-slate-500">Shared Licenses:</span>
                                ${lics.length > 0 ? lics.map(l => `<code class="ml-1 bg-slate-100 px-1 py-0.5 rounded text-[11px] font-mono">${esc(l)}</code>`).join('') : '<span class="text-slate-400 ml-1">None</span>'}
                            </div>
                            <div>
                                <span class="font-semibold text-slate-500">Shared Banks / IFSC:</span>
                                ${banks.length > 0 ? banks.map(b => `<code class="ml-1 bg-slate-100 px-1 py-0.5 rounded text-[11px] font-mono">${esc(b)}</code>`).join('') : '<span class="text-slate-400 ml-1">None</span>'}
                            </div>
                        </div>

                        <!-- Projects in cluster -->
                        <div class="overflow-x-auto mt-2">
                            <table class="w-full text-left text-xs text-slate-600">
                                <thead>
                                    <tr class="text-slate-400 font-medium text-[11px]">
                                        <th class="py-1.5 px-2">Project</th>
                                        <th class="py-1.5 px-2">District</th>
                                        <th class="py-1.5 px-2">Registration No</th>
                                        <th class="py-1.5 px-2">Completion</th>
                                        <th class="py-1.5 px-2">BU Status</th>
                                        <th class="py-1.5 px-2 text-center">Action</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100">
                `;

                (cl.projects || []).forEach(p => {
                    const buGranted = p.has_bu_noc || p.bu_certificate_no;
                    const buBadge = buGranted
                        ? '<span class="text-emerald-700 font-medium">✅ BU Granted</span>'
                        : '<span class="text-amber-700 font-medium">⚠️ No BU</span>';

                    html += `
                        <tr class="hover:bg-slate-50">
                            <td class="py-1.5 px-2 font-medium text-slate-900">${esc(p.name || 'Unnamed')}</td>
                            <td class="py-1.5 px-2 whitespace-nowrap">${esc(p.district || '-')}</td>
                            <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px] text-slate-500">${esc(p.registration_number || '-')}</td>
                            <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px]">${esc(p.completion_date || '-')}</td>
                            <td class="py-1.5 px-2 whitespace-nowrap">${buBadge}</td>
                            <td class="py-1.5 px-2 text-center whitespace-nowrap">
                                <button onclick="openProjectDetail(${p.project_id})" class="text-blue-600 hover:underline text-[11px]">Dossier →</button>
                            </td>
                        </tr>
                    `;
                });

                html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            });
        }

        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<div class="p-6 text-rose-600 text-sm">Failed to resolve clusters: ${esc(err.message)}</div>`;
    }
}

function searchDeveloperCluster(name) {
    const input = document.getElementById('insightsClusterSearchInput');
    if (input) input.value = name;
    renderDeveloperClusters(name);
}
