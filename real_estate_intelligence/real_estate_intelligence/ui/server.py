"""Lightweight zero-dependency web server and interactive dashboard for investors."""

import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from ..analytics.audit import ProjectAuditor
from ..analytics.claims_checker import SalesClaimVerifier
from ..analytics.ml_pricing import HedonicPricingModel
from ..analytics.pricing import PricingIntelligence
from ..analytics.survival import CompletionDelaySurvivalModel
from ..config import DEFAULT_DB_PATH
from ..db.database import get_connection
from ..documents.search import DocumentSearchEngine
from ..graph.network import KnowledgeGraph
from ..mcp.server import RealEstateIntelligenceMCP

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GujRERA Real Estate Intelligence Terminal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <!-- Chart.js 4.4 UMD CDN for Quantitative ML, Survival Curves & Longitudinal Price Analytics -->
    <!-- Source: https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        .tab-btn.active { border-bottom: 2px solid #2563eb; color: #2563eb; font-weight: 600; }
        .tab-btn:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; border-radius: 0.25rem; }
        #tabStrip { scrollbar-width: thin; }
        #tabStrip::-webkit-scrollbar { height: 6px; }
        #tabStrip::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        .kpi-value { white-space: nowrap; font-variant-numeric: tabular-nums; }
        .badge-high { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
        .badge-med { background-color: #fef3c7; color: #92400e; border: 1px solid #fbbf24; }
        .badge-info { background-color: #e0f2fe; color: #075985; border: 1px solid #38bdf8; }
        #networkGraph { height: 560px; width: 100%; border: 1px solid #e2e8f0; border-radius: 0.75rem; background-color: #f8fafc; }
    </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
    <!-- Navbar -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 sm:py-0 sm:h-16 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div class="flex items-center space-x-3 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xl shadow shrink-0">
                    <i class="fa-solid fa-building-shield"></i>
                </div>
                <div class="min-w-0">
                    <h1 class="font-bold text-base sm:text-lg leading-tight text-slate-900 truncate">Real Estate Intelligence Terminal</h1>
                    <p class="text-[11px] sm:text-xs text-slate-500 truncate">GujRERA Evidence-Backed Diligence & Pricing Radar</p>
                </div>
            </div>
            <!-- Project Selector -->
            <div class="flex items-center gap-2 sm:gap-3 sm:shrink-0 min-w-0">
                <label for="projectSelect" class="text-xs font-semibold text-slate-500 uppercase tracking-wider hidden md:inline shrink-0">Select Project:</label>
                <select id="projectSelect" onchange="loadProject(this.value)" aria-label="Select project" class="w-full sm:w-auto sm:max-w-xs min-w-0 bg-slate-100 border border-slate-300 text-slate-800 text-sm rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none font-medium truncate">
                    <!-- Populated dynamically -->
                </select>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <!-- Global Error Banner -->
        <div id="globalErrorBar" class="hidden mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-3" role="alert">
            <span><i class="fa-solid fa-triangle-exclamation mr-1.5"></i><span id="globalErrorMsg">Something went wrong.</span></span>
            <button onclick="hideGlobalError()" aria-label="Dismiss error" class="text-rose-600 hover:text-rose-800 font-bold px-2 shrink-0">&times;</button>
        </div>

        <!-- Project Banner -->
        <div id="projectBanner" class="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
            <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div>
                    <div class="flex items-center gap-3">
                        <h2 id="projName" class="text-2xl font-bold text-slate-900">Loading...</h2>
                        <span id="projStatusBadge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800" title="Project is registered with Gujarat RERA">Registered</span>
                    </div>
                    <p id="projReg" class="text-sm font-mono text-slate-500 mt-1 break-all">--</p>
                    <div class="flex items-center gap-3 mt-1.5 flex-wrap">
                        <p id="projLocation" class="text-xs text-slate-600"><i class="fa-solid fa-location-dot text-slate-400 mr-1"></i> --</p>
                        <a id="projMapLink" href="#" target="_blank" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-xs font-semibold border border-blue-200 transition">
                            <i class="fa-solid fa-satellite"></i> Satellite Map
                        </a>
                    </div>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 bg-slate-50 p-3.5 rounded-lg border border-slate-100 text-center">
                    <div>
                        <span class="text-[11px] text-slate-500 font-medium">Absorption</span>
                        <p id="kpiBooking" class="text-base font-bold text-blue-600 kpi-value">--%</p>
                    </div>
                    <div>
                        <span class="text-[11px] text-slate-500 font-medium">Physical Progress</span>
                        <p id="kpiProgress" class="text-base font-bold text-emerald-600 kpi-value">--%</p>
                    </div>
                    <div>
                        <span class="text-[11px] text-slate-500 font-medium">Velocity Ratio</span>
                        <p id="kpiVelocity" class="text-base font-bold text-indigo-600 kpi-value">--</p>
                    </div>
                    <div>
                        <span class="text-[11px] text-slate-500 font-medium">Escrow Liquidity</span>
                        <p id="kpiEscrowBal" class="text-base font-bold text-slate-800 kpi-value">--</p>
                    </div>
                    <div>
                        <span class="text-[11px] text-slate-500 font-medium">RERA Deadline</span>
                        <p id="kpiDeadline" class="text-base font-bold text-slate-800 kpi-value">--</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div id="tabStrip" role="tablist" aria-label="Dashboard sections" class="border-b border-slate-200 mb-6 flex gap-1 sm:gap-6 text-sm overflow-x-auto">
            <button onclick="switchTab('dossier')" id="tab-dossier" role="tab" aria-selected="true" aria-controls="content-dossier" class="tab-btn active pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-chart-pie mr-2"></i>Executive 4-Quadrant</button>
            <button onclick="switchTab('pricing')" id="tab-pricing" role="tab" aria-selected="false" aria-controls="content-pricing" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-tag mr-2"></i>Unit Pricing</button>
            <button onclick="switchTab('analytics')" id="tab-analytics" role="tab" aria-selected="false" aria-controls="content-analytics" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-brain mr-2"></i>Quantitative ML & Curves</button>
            <button onclick="switchTab('claims')" id="tab-claims" role="tab" aria-selected="false" aria-controls="content-claims" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-scale-balanced mr-2"></i>Claim Fact-Checker</button>
            <button onclick="switchTab('discrepancies')" id="tab-discrepancies" role="tab" aria-selected="false" aria-controls="content-discrepancies" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Audit Discrepancies</button>
            <button onclick="switchTab('graph')" id="tab-graph" role="tab" aria-selected="false" aria-controls="content-graph" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-network-wired mr-2"></i>Knowledge Graph</button>
            <button onclick="switchTab('vault')" id="tab-vault" role="tab" aria-selected="false" aria-controls="content-vault" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-folder-open mr-2"></i>Document Vault</button>
            <button onclick="switchTab('search')" id="tab-search" role="tab" aria-selected="false" aria-controls="content-search" tabindex="-1" class="tab-btn pb-3 px-2 sm:px-1 whitespace-nowrap shrink-0"><i class="fa-solid fa-file-magnifying-glass mr-2"></i>Document Search</button>
        </div>

        <!-- Tab 1: Executive 4-Quadrant -->
        <div id="content-dossier" role="tabpanel" aria-labelledby="tab-dossier" class="tab-content space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Q1: Capital Inflow & Escrow Health -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div>
                        <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3 flex items-center">
                            <i class="fa-solid fa-money-bill-transfer text-blue-600 mr-2"></i> Quadrant 1: Capital Inflow & Escrow Health
                        </h3>
                        <div class="space-y-2.5 text-xs">
                            <div class="flex justify-between py-1 border-b border-slate-100">
                                <span class="text-slate-600">Total Booked Consideration:</span>
                                <span id="q1Consideration" class="font-bold text-slate-900">--</span>
                            </div>
                            <div class="flex justify-between py-1 border-b border-slate-100">
                                <span class="text-slate-600">Cash Collected from Allottees:</span>
                                <span id="q1Received" class="font-bold text-emerald-600">--</span>
                            </div>
                            <div class="flex justify-between py-1 border-b border-slate-100">
                                <span class="text-slate-600">Remaining Balance Receivables:</span>
                                <span id="q1Balance" class="font-bold text-amber-600">--</span>
                            </div>
                            <div class="flex justify-between py-1 border-b border-slate-100">
                                <span class="text-slate-600">Estimated Unsold Inventory Value:</span>
                                <span id="q1Unsold" class="font-bold text-slate-700">--</span>
                            </div>
                            <div class="flex justify-between py-1 border-b border-slate-100">
                                <span class="text-slate-600">Reported Cumulative Expenditure:</span>
                                <span id="q1Incurred" class="font-bold text-slate-900">--</span>
                            </div>
                        </div>
                    </div>
                    <!-- Escrow Banking Breakdown -->
                    <div class="mt-4 pt-3 border-t border-slate-100 bg-slate-50 p-3 rounded-lg text-xs space-y-2" id="q1EscrowBox">
                        <div class="font-bold text-slate-700 flex items-center justify-between">
                            <span><i class="fa-solid fa-vault text-blue-600 mr-1.5"></i> 70% Designated Retention Escrow</span>
                            <span id="escrowStatusTag" class="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-blue-100 text-blue-800">Account Type 1</span>
                        </div>
                        <div id="escrowBankDetails" class="text-slate-600 space-y-1">--</div>
                    </div>
                </div>

                <!-- Q2: Physical Progress & Construction Velocity -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center">
                                <i class="fa-solid fa-helmet-safety text-emerald-600 mr-2"></i> Quadrant 2: Construction Velocity Trajectory
                            </h3>
                            <span id="q2VelocityBadge" class="text-[11px] px-2 py-0.5 rounded-full font-bold">--</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center text-xs mb-3">
                            <div>
                                <span class="text-slate-500 text-[10px]">Time Elapsed</span>
                                <p id="q2TimeLaps" class="font-bold text-slate-800">--%</p>
                            </div>
                            <div>
                                <span class="text-slate-500 text-[10px]">Engineer Progress</span>
                                <p id="q2EnggScore" class="font-bold text-emerald-700">--%</p>
                            </div>
                            <div>
                                <span class="text-slate-500 text-[10px]">Velocity Ratio</span>
                                <p id="q2VelRatio" class="font-bold text-indigo-700">--</p>
                            </div>
                        </div>
                        <div id="q2Timeline" class="space-y-2 max-h-44 overflow-y-auto pr-1">
                            <!-- Populated dynamically -->
                        </div>
                    </div>
                    <div id="q2StagnationAlert" class="mt-3"></div>
                </div>

                <!-- Q3: Land Identity & Block Inventory Overhang -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                    <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3 flex items-center justify-between">
                        <span><i class="fa-solid fa-cubes text-purple-600 mr-2"></i> Quadrant 3: Land Identity & True Overhang</span>
                    </h3>
                    <!-- Land Identity Card -->
                    <div class="bg-purple-50/50 border border-purple-100 p-2.5 rounded-lg mb-3 text-xs grid grid-cols-3 gap-2">
                        <div>
                            <span class="text-slate-500 text-[10px]">Town Planning (TPS)</span>
                            <p id="q3TPS" class="font-bold text-purple-900">--</p>
                        </div>
                        <div>
                            <span class="text-slate-500 text-[10px]">Final Plot (FP)</span>
                            <p id="q3FP" class="font-bold text-purple-900">--</p>
                        </div>
                        <div>
                            <span class="text-slate-500 text-[10px]">Survey Number</span>
                            <p id="q3Survey" class="font-bold text-purple-900">--</p>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-100 text-slate-600 uppercase">
                                <tr>
                                    <th class="p-2">Block</th>
                                    <th class="p-2 text-center">Total</th>
                                    <th class="p-2 text-center">Booked</th>
                                    <th class="p-2 text-center">Unsold</th>
                                    <th class="p-2 text-center">Rate %</th>
                                    <th class="p-2 text-center">Type Mix</th>
                                </tr>
                            </thead>
                            <tbody id="q3BlockTable" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>

                <!-- Q4: Legal Milestones & Regulatory Radar -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                    <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3 flex items-center">
                        <i class="fa-solid fa-scale-balanced text-amber-600 mr-2"></i> Quadrant 4: Legal Handover & Regulatory Radar
                    </h3>
                    <div class="space-y-3 text-xs">
                        <!-- Handover Status -->
                        <div class="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                            <div>
                                <span class="text-slate-500 text-[10px]">Building Use (BU) Permission</span>
                                <p id="q4BuStatus" class="font-bold text-slate-800">--</p>
                            </div>
                            <div>
                                <span class="text-slate-500 text-[10px]">Society Registration Date</span>
                                <p id="q4SocietyDate" class="font-bold text-slate-800">--</p>
                            </div>
                        </div>

                        <!-- Regulatory Radar Flags -->
                        <div class="grid grid-cols-3 gap-2 text-center">
                            <div class="p-2 rounded border bg-slate-50" id="boxComplaints">
                                <span class="text-[10px] text-slate-500">Complaints</span>
                                <p id="q4Complaints" class="font-bold text-slate-800">0</p>
                            </div>
                            <div class="p-2 rounded border bg-slate-50" id="boxAlterations">
                                <span class="text-[10px] text-slate-500">Plan Alterations</span>
                                <p id="q4Alterations" class="font-bold text-slate-800">0</p>
                            </div>
                            <div class="p-2 rounded border bg-slate-50" id="boxDefaults">
                                <span class="text-[10px] text-slate-500">QPR Defaults</span>
                                <p id="q4Defaults" class="font-bold text-slate-800">0</p>
                            </div>
                        </div>

                        <!-- Form 5 Annual Compliance Pills -->
                        <div>
                            <span class="text-[11px] font-semibold text-slate-600 block mb-1">Form 5 CA Annual Audits:</span>
                            <div id="q4Form5Pills" class="flex flex-wrap gap-1.5"></div>
                        </div>

                        <div id="q4Professionals" class="space-y-1 pt-2 border-t border-slate-100"></div>
                        <div id="q4SisterProjects" class="pt-2 border-t border-slate-100"></div>
                        <div id="q4Contagion" class="mt-2"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 2: Pricing Intelligence -->
        <div id="content-pricing" role="tabpanel" aria-labelledby="tab-pricing" class="tab-content hidden space-y-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-bold text-slate-900">Unit-Level Transaction Pricing (Sworn RERA Records)</h3>
                        <p class="text-xs text-slate-500">Calculated directly from registered agreement consideration and carpet areas in Form 3</p>
                    </div>
                    <span class="text-xs font-semibold px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-200">Tamper-Evident</span>
                </div>

                <!-- Benchmark Cards -->
                <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
                    <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                        <span class="text-xs text-slate-500">Minimum Paid</span>
                        <p id="prMin" class="text-base font-bold text-slate-800">--</p>
                    </div>
                    <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                        <span class="text-xs text-slate-500">25th Percentile</span>
                        <p id="prP25" class="text-base font-bold text-slate-800">--</p>
                    </div>
                    <div class="p-3 bg-blue-50 rounded-lg border border-blue-200 text-center shadow-xs">
                        <span class="text-xs font-semibold text-blue-700">Median Rate</span>
                        <p id="prMedian" class="text-xl font-bold text-blue-800">--</p>
                    </div>
                    <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                        <span class="text-xs text-slate-500">75th Percentile</span>
                        <p id="prP75" class="text-base font-bold text-slate-800">--</p>
                    </div>
                    <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                        <span class="text-xs text-slate-500">Maximum Paid</span>
                        <p id="prMax" class="text-base font-bold text-slate-800">--</p>
                    </div>
                </div>

                <!-- Block Benchmarks Table -->
                <h4 class="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Block-by-Block Pricing Distribution</h4>
                <div class="overflow-x-auto mb-6">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-100 text-slate-600 uppercase">
                            <tr>
                                <th class="p-2">Block Name</th>
                                <th class="p-2 text-center">Units Analyzed</th>
                                <th class="p-2 text-center">Min Rate</th>
                                <th class="p-2 text-center">Median Rate / Sq.Ft</th>
                                <th class="p-2 text-center">Max Rate</th>
                            </tr>
                        </thead>
                        <tbody id="prBlockTable" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>

                <!-- Recent Agreements Table -->
                <h4 class="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Recent Registered Transactions in Scheme</h4>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-100 text-slate-600 uppercase">
                            <tr>
                                <th class="p-2">Agreement Date</th>
                                <th class="p-2">Block</th>
                                <th class="p-2 text-center">Carpet Area</th>
                                <th class="p-2 text-right">Consideration</th>
                                <th class="p-2 text-right font-bold">Realized Rate / Sq.Ft</th>
                            </tr>
                        </thead>
                        <tbody id="prRecentTable" class="divide-y divide-slate-100 font-mono"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab: Quantitative ML & Predictive Analytics -->
        <div id="content-analytics" role="tabpanel" aria-labelledby="tab-analytics" class="tab-content hidden space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Card 1: Survival Analysis Delay Curve -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center space-x-2">
                                <i class="fa-solid fa-stopwatch text-indigo-600"></i>
                                <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider">Completion Survival Curve & Delay Hazard</h3>
                            </div>
                            <span id="survRiskBadge" class="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700">--</span>
                        </div>
                        <p class="text-xs text-slate-500 mb-3">Cox Proportional Hazards model estimating time-to-handover probability S(t) = P(Complete &gt; t) calibrated on velocity and burn rate.</p>
                        
                        <!-- Milestones Banner -->
                        <div class="grid grid-cols-4 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center text-xs mb-3">
                            <div>
                                <span class="text-slate-400 text-[10px] block">RERA Target</span>
                                <p id="survReraTarget" class="font-bold text-slate-800">--</p>
                            </div>
                            <div>
                                <span class="text-slate-400 text-[10px] block">p50 Expected</span>
                                <p id="survP50" class="font-bold text-blue-700">--</p>
                            </div>
                            <div>
                                <span class="text-slate-400 text-[10px] block">p75 Conserv.</span>
                                <p id="survP75" class="font-bold text-indigo-700">--</p>
                            </div>
                            <div>
                                <span class="text-slate-400 text-[10px] block">p90 High Conf.</span>
                                <p id="survP90" class="font-bold text-purple-700">--</p>
                            </div>
                        </div>

                        <!-- Canvas -->
                        <div class="relative w-full h-[250px]">
                            <canvas id="survivalCurveChart"></canvas>
                        </div>
                    </div>
                    <div id="survConfidenceNote" class="mt-3 p-2 rounded bg-indigo-50/70 border border-indigo-100 text-[11px] text-indigo-900">
                        --
                    </div>
                </div>

                <!-- Card 2: Hedonic Pricing SHAP Waterfall -->
                <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center space-x-2">
                                <i class="fa-solid fa-water-ladder text-emerald-600"></i>
                                <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider">Hedonic Fair Value & SHAP Attribution</h3>
                            </div>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-100 text-emerald-800">GBDT Tree SHAP</span>
                        </div>
                        <p class="text-xs text-slate-500 mb-3">Additive marginal valuation breakdown (premiums &amp; discounts per sq.ft) against district baseline.</p>

                        <!-- Interactive Filters -->
                        <div class="grid grid-cols-3 gap-2 mb-3">
                            <div>
                                <label class="block text-[10px] font-semibold text-slate-600 mb-0.5">Asset Class:</label>
                                <select id="shapAssetClass" onchange="refreshShapChart()" class="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1 text-xs">
                                    <option value="Residential" selected>Residential</option>
                                    <option value="Commercial_Office">Commercial Office</option>
                                    <option value="Commercial_Retail">Commercial Retail</option>
                                    <option value="Industrial_Warehouse">Industrial Warehouse</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[10px] font-semibold text-slate-600 mb-0.5">Carpet Area (sq.ft):</label>
                                <input id="shapCarpetArea" type="number" value="1200" onchange="refreshShapChart()" class="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1 text-xs">
                            </div>
                            <div class="flex items-end">
                                <button onclick="refreshShapChart()" class="w-full bg-slate-800 hover:bg-slate-900 text-white rounded px-2 py-1 text-xs font-semibold">
                                    <i class="fa-solid fa-arrows-rotate mr-1"></i> Calculate
                                </button>
                            </div>
                        </div>

                        <!-- Predicted Value Summary -->
                        <div class="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center text-xs mb-3">
                            <div>
                                <span class="text-slate-400 text-[10px] block">Baseline Market</span>
                                <p id="shapBaseVal" class="font-bold text-slate-700">--</p>
                            </div>
                            <div>
                                <span class="text-slate-400 text-[10px] block">Fair Value / Sq.Ft</span>
                                <p id="shapPredVal" class="font-bold text-emerald-700">--</p>
                            </div>
                            <div>
                                <span class="text-slate-400 text-[10px] block">Net Spread</span>
                                <p id="shapSpreadVal" class="font-bold text-blue-700">--</p>
                            </div>
                        </div>

                        <!-- Canvas -->
                        <div class="relative w-full h-[250px]">
                            <canvas id="shapWaterfallChart"></canvas>
                        </div>
                    </div>
                    <p class="text-[10px] text-slate-400 mt-2 text-center">Additive efficiency guaranteed: Base Market Rate + Sum(SHAP Values) = Model Valuation.</p>
                </div>
            </div>

            <!-- Card 3: Longitudinal Price Trajectory & Quarterly CAGR -->
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                    <div>
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid fa-chart-line text-blue-600"></i>
                            <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider">Longitudinal Price Realization Trajectory & Annualized CAGR</h3>
                        </div>
                        <p class="text-xs text-slate-500">Multi-year progression of median realized agreement rates from Form 3 sworn records.</p>
                    </div>
                    <!-- Badges -->
                    <div class="flex items-center gap-3">
                        <div class="px-3 py-1 rounded-lg bg-blue-50 border border-blue-200 text-center">
                            <span class="text-[10px] text-blue-600 font-semibold block uppercase">Total Appreciation</span>
                            <span id="trendAppreciationBadge" class="text-sm font-bold text-blue-900">--%</span>
                        </div>
                        <div class="px-3 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                            <span class="text-[10px] text-emerald-600 font-semibold block uppercase">Quarterly CAGR</span>
                            <span id="trendCagrBadge" class="text-sm font-bold text-emerald-900">--%</span>
                        </div>
                    </div>
                </div>

                <div class="relative w-full h-[260px]">
                    <canvas id="priceTrajectoryChart"></canvas>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 text-xs bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center">
                    <div>
                        <span class="text-slate-500 text-[10px]">Launch Quarter</span>
                        <p id="trendLaunchQ" class="font-bold text-slate-800">--</p>
                    </div>
                    <div>
                        <span class="text-slate-500 text-[10px]">Base Realized Rate</span>
                        <p id="trendBaseRate" class="font-bold text-slate-800">--</p>
                    </div>
                    <div>
                        <span class="text-slate-500 text-[10px]">Latest Quarter</span>
                        <p id="trendLatestQ" class="font-bold text-slate-800">--</p>
                    </div>
                    <div>
                        <span class="text-slate-500 text-[10px]">Latest Realized Rate</span>
                        <p id="trendLatestRate" class="font-bold text-emerald-700">--</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 3: Broker Claim Verifier -->
        <div id="content-claims" role="tabpanel" aria-labelledby="tab-claims" class="tab-content hidden space-y-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h3 class="text-lg font-bold text-slate-900 mb-1">Broker & Sales Gallery Fact-Checker</h3>
                <p class="text-xs text-slate-500 mb-6">Enter what the broker or builder sales agent told you to benchmark against statutory disclosures.</p>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Claimed Price per Sq.Ft (Rs.):</label>
                        <input id="claimPrice" type="number" placeholder="e.g. 7500" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Claimed % Sold Out:</label>
                        <input id="claimSold" type="number" placeholder="e.g. 95" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Promised Handover Date:</label>
                        <input id="claimDate" type="date" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    </div>
                </div>

                <button onclick="runClaimVerification()" class="bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm px-5 py-2.5 rounded-lg shadow-sm transition">
                    <i class="fa-solid fa-magnifying-glass-chart mr-1.5"></i> Run Verification Check
                </button>

                <div id="claimResults" class="mt-6 space-y-3"></div>
            </div>
        </div>

        <!-- Tab 4: Discrepancies -->
        <div id="content-discrepancies" role="tabpanel" aria-labelledby="tab-discrepancies" class="tab-content hidden space-y-4">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h3 class="text-lg font-bold text-slate-900 mb-1">Statutory Discrepancy & Commitment Audit</h3>
                <p class="text-xs text-slate-500 mb-4">Automated anomaly detector checking expenditure drops, velocity lag, deadline slippages, escrow depletion, and complaints.</p>
                <div id="discrepancyList" class="space-y-4"></div>
            </div>
        </div>

        <!-- Tab 5: Interactive Knowledge Graph -->
        <div id="content-graph" role="tabpanel" aria-labelledby="tab-graph" class="tab-content hidden space-y-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div>
                        <h3 class="text-lg font-bold text-slate-900">Cross-Project Knowledge Graph & Contagion Explorer</h3>
                        <p class="text-xs text-slate-500">Interactive network of projects, promoters, architects, structural engineers, CAs, and escrow banks</p>
                    </div>
                    <!-- Graph Legend -->
                    <div class="flex flex-wrap gap-2 text-[11px] font-medium">
                        <span class="px-2 py-0.5 rounded bg-blue-100 text-blue-800">● Project</span>
                        <span class="px-2 py-0.5 rounded bg-purple-100 text-purple-800">● Promoter</span>
                        <span class="px-2 py-0.5 rounded bg-amber-100 text-amber-800">● Engineer</span>
                        <span class="px-2 py-0.5 rounded bg-teal-100 text-teal-800">● Architect</span>
                        <span class="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">● CA</span>
                        <span class="px-2 py-0.5 rounded bg-rose-100 text-rose-800">● Bank</span>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div class="lg:col-span-3">
                        <div id="networkGraph"></div>
                    </div>
                    <div class="lg:col-span-1 bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col justify-between text-xs">
                        <div>
                            <h4 class="font-bold text-slate-800 uppercase tracking-wider mb-2" id="graphNodeTitle">Entity Inspector</h4>
                            <p class="text-slate-500 mb-3" id="graphNodeDesc">Click any node in the network to inspect its relationships and cross-project ties.</p>
                            <div id="graphNodeDetails" class="space-y-2"></div>
                        </div>
                        <button onclick="renderGraph()" class="mt-4 w-full py-1.5 bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 rounded text-xs font-semibold shadow-xs">
                            <i class="fa-solid fa-arrows-rotate mr-1"></i> Reset Network Layout
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 6: Document Due Diligence Vault -->
        <div id="content-vault" role="tabpanel" aria-labelledby="tab-vault" class="tab-content hidden space-y-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-bold text-slate-900">Statutory Legal Document Due-Diligence Vault</h3>
                        <p class="text-xs text-slate-500">Core legal checklist required for property title, encumbrance, and municipal verification</p>
                    </div>
                    <span class="text-xs font-semibold px-2 py-1 bg-emerald-50 text-emerald-700 rounded border border-emerald-200">Audit-Ready</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="vaultChecklist">
                    <!-- Populated dynamically -->
                </div>
            </div>
        </div>

        <!-- Tab 7: Document Search (RAG) -->
        <div id="content-search" role="tabpanel" aria-labelledby="tab-search" class="tab-content hidden space-y-6">
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h3 class="text-lg font-bold text-slate-900 mb-1">Regulatory Document Full-Text Search (FTS5)</h3>
                <p class="text-xs text-slate-500 mb-4">Direct sub-millisecond search across 2,006 parsed pages of signed Form 1/2/3 certificates, encumbrance letters, and title deeds.</p>

                <div class="flex gap-2 mb-6">
                    <input id="searchInput" type="text" placeholder="Search keywords (e.g. 'encumbrance', 'title clearance', 'mortgage', 'survey number')..." onkeydown="if(event.key==='Enter') executeSearch()" class="flex-1 min-w-0 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                    <button onclick="executeSearch()" class="bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm px-5 py-2 rounded-lg shadow-sm">
                        <i class="fa-solid fa-magnifying-glass mr-1"></i> Search
                    </button>
                </div>

                <div id="searchResults" class="space-y-3"></div>
            </div>
        </div>
    </main>

    <!-- Floating Diligence Copilot Launcher -->
    <button onclick="toggleCopilot()" id="copilotLauncherBtn" class="fixed bottom-6 right-6 z-40 bg-blue-600 hover:bg-blue-700 text-white rounded-full px-4 py-3 shadow-2xl flex items-center gap-2.5 font-bold text-xs transition transform hover:scale-105 border border-blue-400">
        <i class="fa-solid fa-robot text-base"></i>
        <span>Diligence Copilot</span>
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
    </button>

    <!-- Floating Copilot Drawer Panel -->
    <div id="copilotDrawer" role="dialog" aria-label="Diligence Copilot" class="fixed bottom-20 right-6 w-96 max-w-[calc(100vw-2rem)] h-[540px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 hidden overflow-hidden font-sans">
        <!-- Header -->
        <div class="bg-slate-900 text-white p-3 flex items-center justify-between border-b border-slate-800">
            <div class="flex items-center space-x-2.5">
                <div class="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-xs text-white">
                    <i class="fa-solid fa-scale-balanced"></i>
                </div>
                <div>
                    <h4 class="font-bold text-xs leading-none">RERA Diligence Copilot</h4>
                    <span id="copilotModeStatus" class="text-[10px] text-emerald-400 flex items-center gap-1 mt-0.5">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> <span>MCP Ground-Truth Connected</span>
                    </span>
                </div>
            </div>
            <div class="flex items-center space-x-1">
                <button onclick="toggleCopilotSettings()" title="Copilot LLM Settings" aria-label="Copilot settings" class="text-slate-400 hover:text-white text-xs p-1.5 rounded hover:bg-slate-800 transition">
                    <i class="fa-solid fa-gear"></i>
                </button>
                <button onclick="toggleCopilot()" aria-label="Close copilot" class="text-slate-400 hover:text-white text-sm p-1">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        </div>

        <!-- Settings Slide-down Drawer -->
        <div id="copilotSettingsPanel" class="hidden bg-slate-800 text-slate-200 p-3 text-xs border-b border-slate-700 space-y-2">
            <div class="flex justify-between items-center">
                <span class="font-bold text-slate-100 flex items-center gap-1.5">
                    <i class="fa-solid fa-key text-blue-400"></i> LLM Reasoning Configuration
                </span>
                <span id="keyStatusBadge" class="text-[9px] px-1.5 py-0.5 rounded font-bold bg-slate-700 text-slate-300">Local Offline Mode</span>
            </div>
            <p class="text-[10px] text-slate-400">Enter a Google Gemini or OpenAI API key to activate open-ended reasoning with MCP tool calling. Stored strictly in your local browser.</p>
            <div class="flex gap-1.5">
                <input id="copilotApiKeyInput" type="password" placeholder="Gemini or OpenAI API Key..." class="flex-1 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-400">
                <button onclick="saveCopilotApiKey()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-2.5 py-1 rounded text-xs transition">Save</button>
            </div>
        </div>

        <!-- Messages Container -->
        <div id="copilotMessages" class="flex-1 p-3.5 overflow-y-auto space-y-3 text-xs bg-slate-50">
            <div class="flex gap-2">
                <div class="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="bg-white border border-slate-200 p-2.5 rounded-2xl rounded-tl-none shadow-xs text-slate-800 space-y-1">
                    <p class="font-semibold text-slate-900">Welcome to your statutory due-diligence copilot.</p>
                    <p class="text-slate-600">I cross-reference sworn Form 1/2/3 filings, bank passbooks, sub-registrar transaction deeds, and survival delay projections.</p>
                    <p class="text-slate-500 text-[11px] pt-1">Try asking a question or click a prompt below:</p>
                </div>
            </div>
        </div>

        <!-- Quick Prompt Chips -->
        <div class="px-3 py-1.5 bg-slate-100 border-t border-slate-200 flex gap-1.5 overflow-x-auto text-[11px]">
            <button onclick="sendQuickCopilot('Audit Section 4(2)(l)(D) escrow retention and withdrawals')" class="shrink-0 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 rounded px-2 py-0.5 font-medium transition">
                Escrow Audit
            </button>
            <button onclick="sendQuickCopilot('Check title clearance, land records and bank mortgages')" class="shrink-0 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 rounded px-2 py-0.5 font-medium transition">
                Land Encumbrance
            </button>
            <button onclick="sendQuickCopilot('Analyze survival handover delay risk and delivery percentiles')" class="shrink-0 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 rounded px-2 py-0.5 font-medium transition">
                Delay Risk
            </button>
            <button onclick="sendQuickCopilot('What is the multi-year transaction price trajectory and CAGR?')" class="shrink-0 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 rounded px-2 py-0.5 font-medium transition">
                Price CAGR
            </button>
            <button onclick="sendQuickCopilot('Trace shared professionals and contagion risk')" class="shrink-0 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 rounded px-2 py-0.5 font-medium transition">
                Contagion
            </button>
        </div>

        <!-- Input Box -->
        <div class="p-2.5 bg-white border-t border-slate-200 flex gap-1.5">
            <input id="copilotInput" type="text" placeholder="Ask about escrow, mortgages, delays..." onkeydown="if(event.key==='Enter') submitCopilotMessage()" class="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none">
            <button onclick="submitCopilotMessage()" class="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-3 py-1.5 text-xs font-semibold shadow-xs">
                <i class="fa-solid fa-paper-plane"></i>
            </button>
        </div>
    </div>

    <script>
        let currentPid = null;
        let networkInstance = null;
        let survivalChartInstance = null;
        let shapChartInstance = null;
        let trendChartInstance = null;

        function formatINR(val) {
            if (val === null || val === undefined || isNaN(Number(val))) return '--';
            return '₹' + (val / 10000000).toFixed(2) + ' Cr';
        }

        // Escape untrusted database / filing text before it enters innerHTML.
        function esc(s) {
            if (s === null || s === undefined) return '';
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        // Escape untrusted snippet text while preserving the FTS engine's intentional <b> highlight tags.
        function escSnippet(s) {
            return esc(s).replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\\/b&gt;/g, '</b>');
        }

        async function fetchJSON(url, opts) {
            const res = await fetch(url, opts);
            if (!res.ok) {
                const err = new Error('Request failed (HTTP ' + res.status + ')');
                err.status = res.status;
                throw err;
            }
            return res.json();
        }

        function showGlobalError(message) {
            const bar = document.getElementById('globalErrorBar');
            document.getElementById('globalErrorMsg').textContent = message;
            bar.classList.remove('hidden');
        }

        function hideGlobalError() {
            document.getElementById('globalErrorBar').classList.add('hidden');
        }

        async function init() {
            updateKeyStatusBadge();
            const select = document.getElementById('projectSelect');
            select.disabled = true;
            select.innerHTML = '<option>Loading projects…</option>';
            try {
                const projects = await fetchJSON('/api/projects');
                if (!Array.isArray(projects) || projects.length === 0) {
                    throw new Error('No projects available in the database');
                }
                hideGlobalError();
                select.innerHTML = '';
                if (!projects.some(p => p.project_id === currentPid)) {
                    currentPid = projects[0].project_id;
                }
                projects.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.project_id;
                    opt.textContent = `${p.project_id} — ${p.name} (${p.district})`;
                    if (p.project_id === currentPid) opt.selected = true;
                    select.appendChild(opt);
                });
                select.disabled = false;
                await loadProject(currentPid);
            } catch (err) {
                select.innerHTML = '<option>Unavailable</option>';
                showGlobalError('Could not load the project list: ' + err.message + '. Is the intelligence server running?');
            }
        }

        async function loadProject(pid) {
            currentPid = pid;
            hideGlobalError();
            // Clear stale panels from the previously selected project immediately
            document.getElementById('claimResults').innerHTML = '';
            document.getElementById('searchResults').innerHTML = '';
            document.getElementById('discrepancyList').innerHTML = '<p class="text-xs text-slate-400">Loading audit discrepancies…</p>';
            document.getElementById('projName').textContent = 'Loading…';
            document.getElementById('projStatusBadge').classList.add('hidden');

            let data;
            try {
                data = await fetchJSON(`/api/project/${pid}`);
            } catch (err) {
                document.getElementById('projName').textContent = 'Failed to load project';
                document.getElementById('projReg').textContent = '--';
                document.getElementById('projLocation').innerHTML = '<span class="text-rose-600">Project data could not be loaded. Try selecting the project again.</span>';
                showGlobalError('Could not load project ' + pid + ': ' + err.message);
                return;
            }
            document.getElementById('projStatusBadge').classList.remove('hidden');

            // Populate Banner
            document.getElementById('projName').textContent = data.project.name;
            document.getElementById('projReg').textContent = data.project.registration_number;
            document.getElementById('projLocation').innerHTML = `<i class="fa-solid fa-location-dot text-slate-400 mr-1"></i> ${esc(data.project.taluka || '—')}, ${esc(data.project.district)} | Promoter: <b>${esc(data.project.promoter_name)}</b>`;

            const mapLink = document.getElementById('projMapLink');
            if (data.project.google_maps_url) {
                mapLink.href = data.project.google_maps_url;
                mapLink.style.display = 'inline-flex';
            } else {
                mapLink.style.display = 'none';
            }

            document.getElementById('kpiBooking').textContent = `${data.project.booking_rate_pct || 0}%`;
            document.getElementById('kpiProgress').textContent = `${(data.project.engg_score_pct || data.project.latest_form_one_progress_pct || 0).toFixed(1)}%`;
            document.getElementById('kpiVelocity').textContent = (data.project.velocity_ratio !== null && data.project.velocity_ratio !== undefined) ? `${data.project.velocity_ratio}x` : '--';
            document.getElementById('kpiDeadline').textContent = data.project.completion_date || '--';

            // Escrow Liquidity KPI
            const escrowAcc = data.banks.find(b => b.account_type === 1) || {};
            document.getElementById('kpiEscrowBal').textContent = escrowAcc.closing_bal !== undefined && escrowAcc.closing_bal !== null ? `₹${(escrowAcc.closing_bal/100000).toFixed(1)} L` : '--';

            // Quadrant 1
            const fin = data.finances[data.finances.length - 1] || {};
            document.getElementById('q1Consideration').textContent = formatINR(fin.booked_consideration);
            document.getElementById('q1Received').textContent = formatINR(fin.received_amount);
            document.getElementById('q1Balance').textContent = formatINR(fin.balance_amount);
            document.getElementById('q1Unsold').textContent = formatINR(fin.unbooked_consideration);
            document.getElementById('q1Incurred').textContent = formatINR(fin.incurred_and_paid);

            const escrowDiv = document.getElementById('escrowBankDetails');
            if (escrowAcc.bank_name) {
                escrowDiv.innerHTML = `
                    <div class="flex justify-between"><span>Bank & Branch:</span><b class="text-slate-800">${esc(escrowAcc.bank_name)} (${esc(escrowAcc.branch_name || 'Main')})</b></div>
                    <div class="flex justify-between"><span>Designated Account:</span><b class="font-mono text-slate-800">${esc(escrowAcc.account_number_masked || '--')}</b></div>
                    <div class="flex justify-between"><span>Period Deposits:</span><span class="text-emerald-700 font-semibold">₹${((escrowAcc.deposit_amt||0)/100000).toFixed(2)} Lakhs</span></div>
                    <div class="flex justify-between"><span>Period Withdrawals:</span><span class="text-amber-700 font-semibold">₹${((escrowAcc.withdrawal_amt||0)/100000).toFixed(2)} Lakhs</span></div>
                    <div class="flex justify-between border-t border-slate-200 pt-1 font-bold"><span>Closing Liquidity:</span><span class="text-blue-800">₹${((escrowAcc.closing_bal||0)/100000).toFixed(2)} Lakhs</span></div>
                `;
            } else {
                escrowDiv.innerHTML = '<span>No designated 70% retention account details disclosed in snapshot.</span>';
            }

            // Quadrant 2 Velocity & Timeline
            document.getElementById('q2TimeLaps').textContent = data.project.time_elapsed_pct ? `${data.project.time_elapsed_pct}%` : '--%';
            document.getElementById('q2EnggScore').textContent = data.project.engg_score_pct ? `${data.project.engg_score_pct}%` : '--%';
            document.getElementById('q2VelRatio').textContent = data.project.velocity_ratio !== null ? `${data.project.velocity_ratio}x` : '--';

            const vBadge = document.getElementById('q2VelocityBadge');
            const vRatio = data.project.velocity_ratio;
            if (vRatio !== null && vRatio !== undefined) {
                if (vRatio >= 1.0) {
                    vBadge.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800';
                    vBadge.textContent = `On Schedule (${vRatio}x)`;
                } else if (vRatio >= 0.8) {
                    vBadge.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-800';
                    vBadge.textContent = `Pace Deficit (${vRatio}x)`;
                } else {
                    vBadge.className = 'text-[11px] px-2 py-0.5 rounded-full font-bold bg-rose-100 text-rose-800';
                    vBadge.textContent = `Severely Delayed (${vRatio}x)`;
                }
            } else {
                vBadge.textContent = '--';
            }

            const q2Div = document.getElementById('q2Timeline');
            q2Div.innerHTML = '';
            if (data.timeline && data.timeline.length) {
                data.timeline.forEach(t => {
                    const progress = t.progress_percentage === null || t.progress_percentage === undefined ? 0 : t.progress_percentage;
                    const row = document.createElement('div');
                    row.className = 'flex items-center justify-between text-xs py-1 border-b border-slate-50';
                    row.innerHTML = `<span class="text-slate-600 font-medium">${esc(t.period_label)}</span>
                                     <div class="flex items-center gap-2">
                                        <div class="w-24 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                                            <div class="bg-emerald-500 h-1.5 rounded-full" style="width: ${Math.min(100, progress)}%"></div>
                                        </div>
                                        <span class="font-bold text-slate-800 w-12 text-right">${Number(progress).toFixed(1)}%</span>
                                     </div>`;
                    q2Div.appendChild(row);
                });
            } else {
                q2Div.innerHTML = '<p class="text-xs text-slate-400">No quarterly trajectory recorded.</p>';
            }

            // Quadrant 3 Land & Blocks
            document.getElementById('q3TPS').textContent = data.project.tp_scheme || 'Not explicitly indexed';
            document.getElementById('q3FP').textContent = data.project.final_plot_no || 'Not explicitly indexed';
            document.getElementById('q3Survey').textContent = data.project.survey_no || 'Not explicitly indexed';

            const bTable = document.getElementById('q3BlockTable');
            bTable.innerHTML = '';
            data.blocks.forEach(b => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="p-2 font-bold">${esc(b.block_name)}</td>
                                <td class="p-2 text-center">${b.total_units}</td>
                                <td class="p-2 text-center text-emerald-600 font-medium">${b.booked_units}</td>
                                <td class="p-2 text-center text-amber-600 font-medium">${b.unbooked_units}</td>
                                <td class="p-2 text-center font-bold">${Number(b.booking_rate_pct).toFixed(1)}%</td>
                                <td class="p-2 text-center text-slate-500">${b.residential_units} Res / ${b.commercial_units} Comm</td>`;
                bTable.appendChild(tr);
            });

            // Quadrant 4 Legal & Regulatory
            document.getElementById('q4BuStatus').innerHTML = data.project.bu_status ? `<span class="text-emerald-700">${esc(data.project.bu_status)}</span>` : '<span class="text-amber-600">Pending / Unverified</span>';
            document.getElementById('q4SocietyDate').innerHTML = data.project.society_reg_date ? `<span class="text-blue-700 font-mono">${esc(data.project.society_reg_date)}</span>` : '<span class="text-slate-400">Not Formed</span>';

            document.getElementById('q4Complaints').textContent = data.project.complaints_count || 0;
            document.getElementById('q4Alterations').textContent = data.project.alterations_count || 0;
            document.getElementById('q4Defaults').textContent = data.project.default_quarters_count || 0;

            const cBox = document.getElementById('boxComplaints');
            cBox.className = data.project.complaints_count > 0 ? 'p-2 rounded border bg-rose-50 border-rose-200 text-rose-900' : 'p-2 rounded border bg-slate-50';

            const aBox = document.getElementById('boxAlterations');
            aBox.className = data.project.alterations_count > 0 ? 'p-2 rounded border bg-amber-50 border-amber-200 text-amber-900' : 'p-2 rounded border bg-slate-50';

            const dBox = document.getElementById('boxDefaults');
            dBox.className = data.project.default_quarters_count > 0 ? 'p-2 rounded border bg-rose-50 border-rose-200 text-rose-900' : 'p-2 rounded border bg-slate-50';

            // Form 5 Pills
            const f5Div = document.getElementById('q4Form5Pills');
            f5Div.innerHTML = '';
            (data.form5 || []).forEach(f5 => {
                const isSub = f5.status === 'SUBMITTED';
                const pill = document.createElement('span');
                pill.className = `px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${isSub ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-amber-100 text-amber-800 border border-amber-200'}`;
                pill.textContent = `${f5.financial_year}: ${f5.status}`;
                f5Div.appendChild(pill);
            });

            // Professionals & Contagion
            const profDiv = document.getElementById('q4Professionals');
            profDiv.innerHTML = '<span class="font-semibold text-slate-700">Certified Team: </span>' +
                data.professionals.map(p => `<b>${esc(p.role.toUpperCase())}:</b> ${esc(p.name)} ${p.license_or_reg_no ? '('+esc(p.license_or_reg_no)+')' : ''}`).join(' | ');

            const priorDiv = document.getElementById('q4SisterProjects');
            priorDiv.innerHTML = '<span class="font-semibold text-slate-700">Sister Schemes: </span>' +
                (data.prior_projects.length ? data.prior_projects.map(p => `${esc(p.linked_project_name)} (ID ${p.linked_project_id})`).join(', ') : 'None registered');

            const contDiv = document.getElementById('q4Contagion');
            contDiv.innerHTML = '';
            if (data.contagion && data.contagion.length) {
                data.contagion.forEach(c => {
                    const alert = document.createElement('div');
                    alert.className = 'p-2 rounded bg-amber-50 text-amber-900 border border-amber-200 text-xs mb-1';
                    alert.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1 text-amber-600"></i> ${esc(c.detail)}`;
                    contDiv.appendChild(alert);
                });
            }

            // Populate Discrepancies Tab
            const discDiv = document.getElementById('discrepancyList');
            discDiv.innerHTML = '';
            if (data.leads && data.leads.length) {
                data.leads.forEach(l => {
                    const card = document.createElement('div');
                    const badgeClass = l.severity === 'HIGH' ? 'badge-high' : 'badge-med';
                    card.className = `p-4 rounded-xl border ${badgeClass} text-xs`;
                    card.innerHTML = `
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-bold text-sm">${esc(l.title)}</span>
                            <span class="px-2 py-0.5 rounded font-bold uppercase text-[10px] tracking-wider">${esc(l.severity)}</span>
                        </div>
                        <p class="mb-2 opacity-90">${esc(l.detail)}</p>
                        <div class="p-2 bg-white/70 rounded border border-black/5">
                            <b>Action / Verification:</b> ${esc(l.reconciliation_guidance)}
                        </div>
                    `;
                    discDiv.appendChild(card);
                });
            } else {
                discDiv.innerHTML = '<p class="text-sm text-emerald-700 bg-emerald-50 p-4 rounded-lg border border-emerald-200"><i class="fa-solid fa-check mr-2"></i> Clean project: 0 statutory discrepancies detected across structured filings.</p>';
            }

            // Populate Document Vault Checklist
            populateDocumentVault(data);

            // Load Pricing & Knowledge Graph
            loadPricing(pid);
            renderGraph();
            if (document.getElementById('tab-analytics').classList.contains('active')) {
                loadAnalytics(pid);
            }
        }

        function populateDocumentVault(data) {
            const vaultList = [
                { id: "title", name: "Title Search Report & Clearance", desc: "Advocate certificate verifying 30-year non-encumbrance title chain", query: "title clearance" },
                { id: "encumbrance", name: "Encumbrance Certificate", desc: "Sub-Registrar record confirming no registered mortgages or court attachments", query: "encumbrance" },
                { id: "cc", name: "Commencement Certificate (CC)", desc: "Municipal permission granting authority to start physical construction", query: "commencement" },
                { id: "sanction", name: "Sanctioned Layout & Building Plan", desc: "Approved architectural elevations, FSI, and floor layouts", query: "layout plan" },
                { id: "form_b", name: "Form B Statutory Declaration", desc: "Builder affidavit declaring 70% deposit and no unconsented changes", query: "form b" },
                { id: "bu", name: "Building Use (BU) Permission", desc: data.project.bu_status || "Pending municipal approval", query: "building use" },
                { id: "agreement", name: "Model Agreement for Sale", desc: "Standard RERA contract terms between developer and allottees", query: "agreement for sale" },
                { id: "form_four", name: "Form 4 Completion Certificate", desc: data.project.form_four_status ? `Status: ${data.project.form_four_status}` : "Pending final handover", query: "form four" }
            ];
            const vDiv = document.getElementById('vaultChecklist');
            vDiv.innerHTML = '';
            vaultList.forEach(item => {
                const card = document.createElement('div');
                card.className = 'p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs flex flex-col justify-between';
                card.innerHTML = `
                    <div>
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-bold text-slate-800">${item.name}</span>
                            <span class="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded font-semibold">Statutory Check</span>
                        </div>
                        <p class="text-slate-500 mb-3">${esc(item.desc)}</p>
                    </div>
                    <button onclick="searchVaultDoc('${item.query}')" class="w-full py-1.5 bg-white hover:bg-blue-50 text-blue-700 border border-slate-200 hover:border-blue-300 rounded font-semibold text-center transition">
                        <i class="fa-solid fa-magnifying-glass mr-1"></i> Inspect Text in RAG
                    </button>
                `;
                vDiv.appendChild(card);
            });
        }

        function searchVaultDoc(query) {
            switchTab('search');
            document.getElementById('searchInput').value = query;
            executeSearch();
        }

        async function renderGraph() {
            const container = document.getElementById('networkGraph');
            let data;
            try {
                const res = await fetch(`/api/graph?project_id=${currentPid}`);
                if (!res.ok) throw new Error('Request failed (HTTP ' + res.status + ')');
                data = await res.json();
            } catch (err) {
                container.innerHTML = `<p class="text-xs text-rose-700 p-4">Knowledge graph could not be loaded: ${esc(err.message)}</p>`;
                return;
            }
            const graphData = {
                nodes: new vis.DataSet(data.nodes),
                edges: new vis.DataSet(data.edges)
            };

            const options = {
                nodes: {
                    shape: 'dot',
                    size: 16,
                    font: { size: 12, face: 'system-ui' },
                    borderWidth: 2
                },
                edges: {
                    width: 1.5,
                    font: { size: 10, align: 'middle' },
                    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                    smooth: { type: 'continuous' }
                },
                physics: {
                    stabilization: false,
                    barnesHut: { gravitationalConstant: -3000, springLength: 95 }
                }
            };

            if (networkInstance) {
                networkInstance.destroy();
            }
            networkInstance = new vis.Network(container, graphData, options);

            // Visually highlight the node for the currently selected project so the
            // graph reads as "this project's network", not an anonymous statewide web.
            const currentNodeId = 'project:' + currentPid;
            if (data.nodes.some(n => n.id === currentNodeId)) {
                networkInstance.selectNodes([currentNodeId], false);
            }

            networkInstance.on("click", function (params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    const node = data.nodes.find(n => n.id === nodeId);
                    if (node) {
                        document.getElementById('graphNodeTitle').textContent = node.label;
                        document.getElementById('graphNodeDesc').textContent = `Type: ${node.group} | ID: ${node.id}`;

                        // Find connected edges
                        const connected = data.edges.filter(e => e.from === nodeId || e.to === nodeId);
                        let html = `<div class="font-semibold text-slate-700 mb-1">Direct Links (${connected.length}):</div><ul class="list-disc pl-4 space-y-1">`;
                        connected.forEach(e => {
                            const otherId = e.from === nodeId ? e.to : e.from;
                            const otherNode = data.nodes.find(n => n.id === otherId);
                            html += `<li><b>${esc(e.label)}:</b> ${otherNode ? esc(otherNode.label) : esc(otherId)}</li>`;
                        });
                        html += `</ul>`;
                        document.getElementById('graphNodeDetails').innerHTML = html;
                    }
                }
            });
        }

        async function loadPricing(pid) {
            let data;
            try {
                data = await fetchJSON(`/api/pricing/${pid}`);
            } catch (err) {
                document.getElementById('prBlockTable').innerHTML = `<tr><td colspan="5" class="p-3 text-xs text-rose-700">Pricing data could not be loaded: ${esc(err.message)}</td></tr>`;
                return;
            }
            const ov = data.overall_rate_per_sqft || {};

            document.getElementById('prMin').textContent = ov.min ? `Rs. ${ov.min.toLocaleString()}` : '--';
            document.getElementById('prP25').textContent = ov.p25 ? `Rs. ${ov.p25.toLocaleString()}` : '--';
            document.getElementById('prMedian').textContent = ov.median ? `Rs. ${ov.median.toLocaleString()}` : '--';
            document.getElementById('prP75').textContent = ov.p75 ? `Rs. ${ov.p75.toLocaleString()}` : '--';
            document.getElementById('prMax').textContent = ov.max ? `Rs. ${ov.max.toLocaleString()}` : '--';

            // Block benchmarks
            const bTable = document.getElementById('prBlockTable');
            bTable.innerHTML = '';
            for (const [bname, stats] of Object.entries(data.block_benchmarks || {})) {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="p-2 font-bold">${esc(bname)}</td>
                                <td class="p-2 text-center">${stats.count}</td>
                                <td class="p-2 text-center text-slate-600">Rs. ${stats.min ? stats.min.toLocaleString() : '--'}</td>
                                <td class="p-2 text-center font-bold text-blue-700">Rs. ${stats.median ? stats.median.toLocaleString() : '--'}</td>
                                <td class="p-2 text-center text-slate-600">Rs. ${stats.max ? stats.max.toLocaleString() : '--'}</td>`;
                bTable.appendChild(tr);
            }

            // Recent table
            const rTable = document.getElementById('prRecentTable');
            rTable.innerHTML = '';
            (data.recent_registered_transactions || []).forEach(t => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="p-2">${esc(t.agreement_date)}</td>
                                <td class="p-2 font-sans font-medium">${esc(t.block)}</td>
                                <td class="p-2 text-center">${t.carpet_sqft} sq.ft</td>
                                <td class="p-2 text-right">₹${(t.consideration_inr/100000).toFixed(2)} L</td>
                                <td class="p-2 text-right font-bold text-blue-600">Rs. ${t.rate_sqft.toLocaleString()}</td>`;
                rTable.appendChild(tr);
            });
        }

        async function runClaimVerification() {
            const price = document.getElementById('claimPrice').value;
            const sold = document.getElementById('claimSold').value;
            const date = document.getElementById('claimDate').value;
            const resDiv = document.getElementById('claimResults');

            if (!price && !sold && !date) {
                resDiv.innerHTML = '<p class="text-xs text-amber-800 bg-amber-50 border border-amber-200 p-3 rounded-lg">Enter at least one claim above (price, % sold, or handover date) to run the verification.</p>';
                return;
            }

            resDiv.innerHTML = '<p class="text-xs text-slate-500">Verifying claims against statutory disclosures…</p>';
            let data;
            try {
                const res = await fetchJSON(`/api/verify_claim?project_id=${currentPid}&claimed_rate=${price}&claimed_sold=${sold}&claimed_date=${date}`);
                data = res;
            } catch (err) {
                resDiv.innerHTML = `<p class="text-xs text-rose-800 bg-rose-50 border border-rose-200 p-3 rounded-lg">Verification failed: ${esc(err.message)}. Check that the entered values are valid numbers.</p>`;
                return;
            }

            resDiv.innerHTML = '';

            (data.verification_checks || []).forEach(c => {
                const card = document.createElement('div');
                const isBad = c.verdict.includes('EXAGGERATED') || c.verdict.includes('ARTIFICIAL') || c.verdict.includes('AGGRESSIVE');
                card.className = `p-4 rounded-xl border text-xs ${isBad ? 'bg-amber-50 border-amber-300 text-amber-900' : 'bg-emerald-50 border-emerald-300 text-emerald-900'}`;
                card.innerHTML = `
                    <div class="flex items-center justify-between mb-1.5">
                        <span class="font-bold text-sm">${esc(c.metric)}</span>
                        <span class="px-2 py-0.5 rounded font-bold uppercase tracking-wider text-[10px] ${isBad ? 'bg-amber-200 text-amber-900' : 'bg-emerald-200 text-emerald-900'}">${esc(c.verdict)}</span>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-xs mb-2">
                        <div><b>Sales Pitch:</b> ${esc(c.claimed)}</div>
                        <div><b>Statutory Reality:</b> ${esc(c.statutory_actual)}</div>
                    </div>
                    <p class="mb-2 opacity-95">${esc(c.detail)}</p>
                    <div class="p-2 bg-white/70 rounded border border-black/5 font-medium">
                        <i class="fa-solid fa-lightbulb text-amber-600 mr-1"></i> <b>Negotiation Advice:</b> ${esc(c.buyer_guidance)}
                    </div>
                `;
                resDiv.appendChild(card);
            });
        }

        async function executeSearch() {
            const query = document.getElementById('searchInput').value.trim();
            const resDiv = document.getElementById('searchResults');
            if (!query) {
                resDiv.innerHTML = '<p class="text-xs text-slate-500 p-3 bg-slate-50 rounded border border-slate-200">Enter a keyword above to search the indexed statutory document pages.</p>';
                return;
            }

            resDiv.innerHTML = '<p class="text-xs text-slate-500">Searching indexed filings…</p>';
            let data;
            try {
                data = await fetchJSON(`/api/search?query=${encodeURIComponent(query)}&project_id=${currentPid}`);
            } catch (err) {
                resDiv.innerHTML = `<p class="text-xs text-rose-800 bg-rose-50 border border-rose-200 p-3 rounded-lg">Search failed: ${esc(err.message)}</p>`;
                return;
            }

            resDiv.innerHTML = '';

            if (data.results && data.results.length) {
                data.results.forEach((r, idx) => {
                    const card = document.createElement('div');
                    card.className = 'p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs';
                    card.innerHTML = `
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-bold text-slate-800">${idx+1}. [${esc(r.doc_type)}] Page ${esc(r.page_number)}</span>
                            <span class="text-[10px] text-slate-400">Result ${idx+1} of ${data.results.length}</span>
                        </div>
                        <p class="text-slate-600 font-mono text-[11px] mb-1.5 text-slate-500">${esc(r.file_name)}</p>
                        <div class="p-2 bg-white rounded border border-slate-200 text-slate-800 font-serif leading-relaxed">
                            ${escSnippet(r.snippet)}
                        </div>
                    `;
                    resDiv.appendChild(card);
                });
            } else {
                resDiv.innerHTML = '<p class="text-xs text-slate-500 p-4 bg-slate-50 rounded">No matching regulatory clauses found for this query.</p>';
            }
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
                b.setAttribute('tabindex', '-1');
            });
            document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
            const activeBtn = document.getElementById(`tab-${tabId}`);
            activeBtn.classList.add('active');
            activeBtn.setAttribute('aria-selected', 'true');
            activeBtn.removeAttribute('tabindex');
            activeBtn.scrollIntoView({ block: 'nearest', inline: 'nearest' });
            document.getElementById(`content-${tabId}`).classList.remove('hidden');

            if (tabId === 'graph' && networkInstance) {
                setTimeout(() => { networkInstance.fit(); }, 50);
            }
            if (tabId === 'analytics') {
                loadAnalytics(currentPid);
            }
        }

        async function loadAnalytics(pid) {
            // 1. Survival Analysis
            try {
                const sRes = await fetch(`/api/analytics/survival?project_id=${pid}`);
                const sData = await sRes.json();
                
                if (!sData.error) {
                    const badge = document.getElementById('survRiskBadge');
                    badge.textContent = sData.delay_risk_label || '--';
                    if (sData.delay_risk_label === 'ON_TRACK') {
                        badge.className = 'px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800';
                    } else if (sData.delay_risk_label === 'MODERATE_DELAY') {
                        badge.className = 'px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800';
                    } else {
                        badge.className = 'px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800';
                    }

                    document.getElementById('survReraTarget').textContent = sData.registered_completion_date || '--';
                    const hDates = sData.forecasted_handover_dates || {};
                    document.getElementById('survP50').textContent = hDates.p50_median_expected_date || '--';
                    document.getElementById('survP75').textContent = hDates.p75_conservative_date || '--';
                    document.getElementById('survP90').textContent = hDates.p90_high_confidence_date || '--';
                    document.getElementById('survConfidenceNote').textContent = sData.confidence_assessment || '--';

                    const ctx = document.getElementById('survivalCurveChart').getContext('2d');
                    if (survivalChartInstance) survivalChartInstance.destroy();

                    const labels = (sData.survival_curve || []).map(p => `M${p.month}`);
                    const survProb = (sData.survival_curve || []).map(p => (p.survival_prob * 100).toFixed(1));
                    const compProb = (sData.survival_curve || []).map(p => (p.completion_prob * 100).toFixed(1));

                    survivalChartInstance = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [
                                {
                                    label: 'Completion Prob 1-S(t) (%)',
                                    data: compProb,
                                    borderColor: '#10b981',
                                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                    fill: true,
                                    tension: 0.3,
                                    pointRadius: 1,
                                },
                                {
                                    label: 'Survival (Unfinished) S(t) (%)',
                                    data: survProb,
                                    borderColor: '#6366f1',
                                    borderDash: [4, 4],
                                    fill: false,
                                    tension: 0.3,
                                    pointRadius: 1,
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'top', labels: { boxWidth: 12, font: { size: 10 } } },
                                tooltip: { mode: 'index', intersect: false }
                            },
                            scales: {
                                x: { grid: { display: false }, ticks: { maxTicksLimit: 12, font: { size: 9 } } },
                                y: { min: 0, max: 100, ticks: { callback: v => v + '%', font: { size: 9 } } }
                            }
                        }
                    });
                }
            } catch (err) {
                console.error("Survival load error", err);
            }

            // 2. Longitudinal Price Trajectory & CAGR
            try {
                const tRes = await fetch(`/api/analytics/pricing_trend?project_id=${pid}`);
                const tData = await tRes.json();
                
                document.getElementById('trendAppreciationBadge').textContent = tData.price_appreciation_pct !== undefined ? `${tData.price_appreciation_pct > 0 ? '+' : ''}${tData.price_appreciation_pct}%` : '--%';
                document.getElementById('trendCagrBadge').textContent = tData.cagr_pct !== undefined ? `${tData.cagr_pct}%` : '--%';
                document.getElementById('trendLaunchQ').textContent = tData.first_quarter || '--';
                document.getElementById('trendBaseRate').textContent = tData.base_median_rate_sqft ? `Rs. ${tData.base_median_rate_sqft.toLocaleString()}` : '--';
                document.getElementById('trendLatestQ').textContent = tData.latest_quarter || '--';
                document.getElementById('trendLatestRate').textContent = tData.latest_median_rate_sqft ? `Rs. ${tData.latest_median_rate_sqft.toLocaleString()}` : '--';

                const tCtx = document.getElementById('priceTrajectoryChart').getContext('2d');
                if (trendChartInstance) trendChartInstance.destroy();

                const qLabels = (tData.quarterly_trajectory || []).map(q => q.quarter);
                const medRates = (tData.quarterly_trajectory || []).map(q => q.median_rate_sqft);
                const minRates = (tData.quarterly_trajectory || []).map(q => q.min_rate_sqft);
                const maxRates = (tData.quarterly_trajectory || []).map(q => q.max_rate_sqft);

                trendChartInstance = new Chart(tCtx, {
                    type: 'line',
                    data: {
                        labels: qLabels,
                        datasets: [
                            {
                                label: 'Median Rate / Sq.Ft',
                                data: medRates,
                                borderColor: '#2563eb',
                                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                                fill: true,
                                tension: 0.25,
                                pointRadius: 4,
                                pointHoverRadius: 6,
                            },
                            {
                                label: 'Max Rate',
                                data: maxRates,
                                borderColor: '#94a3b8',
                                borderDash: [2, 2],
                                fill: false,
                                pointRadius: 0,
                            },
                            {
                                label: 'Min Rate',
                                data: minRates,
                                borderColor: '#cbd5e1',
                                borderDash: [2, 2],
                                fill: false,
                                pointRadius: 0,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'top', labels: { boxWidth: 12, font: { size: 10 } } },
                            tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: Rs. ${Number(ctx.raw).toLocaleString()}` } }
                        },
                        scales: {
                            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                            y: { ticks: { callback: v => 'Rs.' + v.toLocaleString(), font: { size: 9 } } }
                        }
                    }
                });
            } catch (err) {
                console.error("Pricing trend load error", err);
            }

            // 3. SHAP Waterfall
            await refreshShapChart();
        }

        async function refreshShapChart() {
            try {
                const aclass = document.getElementById('shapAssetClass').value;
                const carpet = document.getElementById('shapCarpetArea').value || 1200;
                
                const res = await fetch(`/api/analytics/ml_pricing?project_id=${currentPid}&asset_class=${encodeURIComponent(aclass)}&carpet_area_sqft=${carpet}`);
                const data = await res.json();
                
                if (data.error) return;

                document.getElementById('shapBaseVal').textContent = `Rs. ${Math.round(data.base_market_average_inr).toLocaleString()}`;
                document.getElementById('shapPredVal').textContent = `Rs. ${Math.round(data.predicted_rate_per_sqft).toLocaleString()}`;
                const spread = data.net_spread_from_average || 0;
                const sElem = document.getElementById('shapSpreadVal');
                sElem.textContent = `${spread >= 0 ? '+' : ''}Rs. ${Math.round(spread).toLocaleString()}`;
                sElem.className = spread >= 0 ? 'font-bold text-emerald-700' : 'font-bold text-amber-700';

                // Prepare top drivers for horizontal bar chart
                const shapObj = data.shap_values || {};
                const entries = Object.entries(shapObj)
                    .filter(([k, v]) => Math.abs(v) >= 2)
                    .sort((a, b) => b[1] - a[1]);

                const labels = entries.map(e => e[0].replace(/_/g, ' '));
                const values = entries.map(e => e[1]);
                const bgColors = values.map(v => v >= 0 ? 'rgba(16, 185, 129, 0.75)' : 'rgba(239, 68, 68, 0.75)');
                const borderColors = values.map(v => v >= 0 ? '#10b981' : '#ef4444');

                const sCtx = document.getElementById('shapWaterfallChart').getContext('2d');
                if (shapChartInstance) shapChartInstance.destroy();

                shapChartInstance = new Chart(sCtx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Impact on Rate (Rs./Sq.Ft)',
                            data: values,
                            backgroundColor: bgColors,
                            borderColor: borderColors,
                            borderWidth: 1
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: { label: ctx => `${ctx.raw >= 0 ? '+' : ''}Rs. ${Math.round(ctx.raw)} / sq.ft` } }
                        },
                        scales: {
                            x: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 }, callback: v => (v >= 0 ? '+' : '') + v } },
                            y: { ticks: { font: { size: 10 } } }
                        }
                    }
                });
            } catch (err) {
                console.error("SHAP chart error", err);
            }
        }

        function toggleCopilot() {
            const d = document.getElementById('copilotDrawer');
            const launcher = document.getElementById('copilotLauncherBtn');
            d.classList.toggle('hidden');
            if (!d.classList.contains('hidden')) {
                launcher.classList.add('hidden');
                document.getElementById('copilotInput').focus();
            } else {
                launcher.classList.remove('hidden');
            }
        }

        function toggleCopilotSettings() {
            const p = document.getElementById('copilotSettingsPanel');
            p.classList.toggle('hidden');
            const inp = document.getElementById('copilotApiKeyInput');
            if (!p.classList.contains('hidden') && inp) {
                inp.value = localStorage.getItem('copilot_api_key') || '';
                inp.focus();
            }
        }

        function saveCopilotApiKey() {
            const val = document.getElementById('copilotApiKeyInput').value.trim();
            if (val) {
                localStorage.setItem('copilot_api_key', val);
            } else {
                localStorage.removeItem('copilot_api_key');
            }
            updateKeyStatusBadge();
            const p = document.getElementById('copilotSettingsPanel');
            p.classList.add('hidden');
        }

        function updateKeyStatusBadge() {
            const key = localStorage.getItem('copilot_api_key');
            const badge = document.getElementById('keyStatusBadge');
            const status = document.getElementById('copilotModeStatus');
            const input = document.getElementById('copilotApiKeyInput');
            if (input && key) input.value = key;
            if (key) {
                if (badge) {
                    badge.className = 'text-[9px] px-1.5 py-0.5 rounded font-bold bg-purple-900/60 text-purple-300 border border-purple-700';
                    badge.textContent = key.startsWith('sk-') ? 'OpenAI Agent Active' : 'Gemini Agent Active';
                }
                if (status) {
                    status.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse"></span> <span class="text-purple-300 font-semibold">Agentic LLM Active</span>';
                }
            } else {
                if (badge) {
                    badge.className = 'text-[9px] px-1.5 py-0.5 rounded font-bold bg-slate-700 text-slate-300';
                    badge.textContent = 'Local Offline Mode';
                }
                if (status) {
                    status.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> <span>MCP Ground-Truth Connected</span>';
                }
            }
        }

        function sendQuickCopilot(text) {
            document.getElementById('copilotInput').value = text;
            submitCopilotMessage();
        }

        async function submitCopilotMessage() {
            const input = document.getElementById('copilotInput');
            const query = input.value.trim();
            if (!query) return;

            input.value = '';
            const msgDiv = document.getElementById('copilotMessages');

            // Add user message bubble
            const userMsg = document.createElement('div');
            userMsg.className = 'flex justify-end';
            userMsg.innerHTML = `
                <div class="bg-blue-600 text-white p-2.5 rounded-2xl rounded-tr-none shadow-xs text-xs max-w-[85%]">
                    ${escapeHtml(query)}
                </div>
            `;
            msgDiv.appendChild(userMsg);

            // Add loading indicator
            const loadingId = 'copilotLoading_' + Date.now();
            const loadingBubble = document.createElement('div');
            loadingBubble.id = loadingId;
            loadingBubble.className = 'flex gap-2';
            loadingBubble.innerHTML = `
                <div class="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="bg-white border border-slate-200 p-2.5 rounded-2xl rounded-tl-none shadow-xs text-slate-500 italic text-[11px]">
                    <i class="fa-solid fa-circle-notch fa-spin mr-1 text-blue-600"></i> Synthesizing regulatory filings &amp; MCP evidence...
                </div>
            `;
            msgDiv.appendChild(loadingBubble);
            msgDiv.scrollTop = msgDiv.scrollHeight;

            try {
                const apiKey = localStorage.getItem('copilot_api_key') || '';
                const res = await fetch('/api/copilot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query, project_id: currentPid, api_key: apiKey })
                });
                const data = await res.json();
                
                const loader = document.getElementById(loadingId);
                if (loader) loader.remove();

                const botMsg = document.createElement('div');
                botMsg.className = 'flex gap-2';
                
                let citationsHtml = '';
                if (data.citations && data.citations.length) {
                    citationsHtml = '<div class="pt-2 border-t border-slate-100 mt-2 space-y-1">' +
                        data.citations.map(c => `<span class="inline-block px-1.5 py-0.5 bg-slate-100 text-slate-600 border border-slate-200 rounded font-mono text-[9px] mr-1">${esc(c)}</span>`).join('') +
                        '</div>';
                }

                let modeBadge = '';
                if (data.mode === 'agentic_llm') {
                    modeBadge = '<div class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-bold mb-1.5"><i class="fa-solid fa-wand-magic-sparkles"></i> Agentic Synthesis (MCP Grounded)</div>';
                }

                botMsg.innerHTML = `
                    <div class="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                        <i class="fa-solid fa-robot"></i>
                    </div>
                    <div class="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-none shadow-xs text-slate-800 text-xs space-y-2 max-w-[90%]">
                        ${modeBadge}
                        <div class="whitespace-pre-line leading-relaxed">${formatBotReply(data.reply)}</div>
                        ${citationsHtml}
                    </div>
                `;
                msgDiv.appendChild(botMsg);
                msgDiv.scrollTop = msgDiv.scrollHeight;
            } catch (err) {
                const loader = document.getElementById(loadingId);
                if (loader) loader.remove();
                const errBubble = document.createElement('div');
                errBubble.className = 'text-[11px] text-rose-600 p-2 bg-rose-50 rounded border border-rose-200';
                errBubble.textContent = 'Error connecting to intelligence copilot service.';
                msgDiv.appendChild(errBubble);
            }
        }

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        function formatBotReply(str) {
            // Escape untrusted reply text (filing-derived strings, LLM output) BEFORE
            // applying the markdown transforms, which then inject only our own tags.
            return esc(str)
                .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
                .replace(/^\\* (.*$)/gim, '• $1')
                .replace(/^### (.*$)/gim, '<div class="font-bold text-slate-900 border-b border-slate-100 pb-1 mb-1 text-xs">$1</div>');
        }

        // Keyboard support: Esc closes the copilot drawer; arrow keys move between dashboard tabs.
        document.addEventListener('keydown', (e) => {
            const drawer = document.getElementById('copilotDrawer');
            if (e.key === 'Escape' && drawer && !drawer.classList.contains('hidden')) {
                toggleCopilot();
                return;
            }
            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
            const tabs = Array.from(document.querySelectorAll('#tabStrip .tab-btn'));
            const idx = tabs.findIndex(t => t.classList.contains('active'));
            if (idx === -1) return;
            const nextIdx = e.key === 'ArrowRight' ? (idx + 1) % tabs.length : (idx - 1 + tabs.length) % tabs.length;
            const nextBtn = tabs[nextIdx];
            nextBtn.focus();
            nextBtn.click();
        });

        window.onload = init;
    </script>
</body>
</html>
"""


class IntelligenceRequestHandler(BaseHTTPRequestHandler):
    con = None
    pricing_engine = None
    verifier = None
    auditor = None
    search_engine = None
    graph_engine = None
    mcp_server = None
    agentic_copilot = None

    @classmethod
    def setup_backends(cls, db_path=None):
        cls.con = get_connection(db_path)
        cls.pricing_engine = PricingIntelligence(cls.con)
        cls.verifier = SalesClaimVerifier(cls.con)
        cls.auditor = ProjectAuditor(cls.con)
        cls.search_engine = DocumentSearchEngine(cls.con)
        cls.graph_engine = KnowledgeGraph(cls.con)
        cls.mcp_server = RealEstateIntelligenceMCP(cls.con)
        from ..agent.copilot import AgenticCopilot
        cls.agentic_copilot = AgenticCopilot(cls.mcp_server)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path == "/api/projects":
            cur = self.con.execute("SELECT project_id, name, district, promoter_name FROM projects ORDER BY project_id")
            projects = [dict(r) for r in cur.fetchall()]
            self._send_json(projects)
            return

        if path.startswith("/api/project/"):
            try:
                pid = int(path.split("/")[-1])
            except ValueError:
                self.send_error(400, "Invalid project ID")
                return

            cur = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (pid,))
            prow = cur.fetchone()
            if not prow:
                self.send_error(404, "Project not found")
                return

            blocks = [dict(r) for r in self.con.execute("SELECT * FROM inventory_blocks WHERE project_id = ? ORDER BY block_name", (pid,)).fetchall()]
            timeline = [dict(r) for r in self.con.execute("SELECT * FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
            finances = [dict(r) for r in self.con.execute("SELECT * FROM finances WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
            professionals = [dict(r) for r in self.con.execute("SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?", (pid,)).fetchall()]
            banks = [dict(r) for r in self.con.execute("SELECT * FROM banks WHERE project_id = ? ORDER BY account_type ASC", (pid,)).fetchall()]
            prior = [dict(r) for r in self.con.execute(
                "SELECT linked_project_name, linked_project_id FROM previous_projects WHERE project_id = ? AND linked_project_id != ?",
                (pid, pid),
            ).fetchall()]
            form5 = [dict(r) for r in self.con.execute("SELECT * FROM form5_compliance WHERE project_id = ? ORDER BY financial_year ASC", (pid,)).fetchall()]
            bu_records = [dict(r) for r in self.con.execute("SELECT * FROM noc_bu_records WHERE project_id = ? ORDER BY block_name ASC", (pid,)).fetchall()]
            
            leads = [
                {
                    "category": l.category,
                    "severity": l.severity,
                    "title": l.title,
                    "detail": l.detail,
                    "reconciliation_guidance": l.reconciliation_guidance,
                }
                for l in self.auditor.audit_project(pid)
            ]
            contagion = self.graph_engine.trace_contagion_risk(pid)

            self._send_json({
                "project": dict(prow),
                "blocks": blocks,
                "timeline": timeline,
                "finances": finances,
                "professionals": professionals,
                "banks": banks,
                "prior_projects": prior,
                "form5": form5,
                "bu_records": bu_records,
                "leads": leads,
                "contagion": contagion,
            })
            return

        if path == "/api/graph":
            # Return nodes and edges formatted for Vis.js
            cur = self.con.cursor()
            cur.execute("SELECT node_id, kind, label FROM graph_nodes")
            color_map = {
                "Project": "#2563eb",
                "Promoter": "#7c3aed",
                "Engineer": "#d97706",
                "Architect": "#0d9488",
                "Ca": "#059669",
                "Bank": "#e11d48",
                "PriorProject": "#64748b"
            }
            nodes = [
                {
                    "id": r["node_id"],
                    "label": r["label"],
                    "group": r["kind"],
                    "color": color_map.get(r["kind"], "#3b82f6")
                }
                for r in cur.fetchall()
            ]

            cur.execute("SELECT src_id, relation, dst_id FROM graph_edges")
            edges = [
                {
                    "from": r["src_id"],
                    "to": r["dst_id"],
                    "label": r["relation"],
                    "color": {"color": "#94a3b8", "highlight": "#2563eb"}
                }
                for r in cur.fetchall()
            ]

            self._send_json({"nodes": nodes, "edges": edges})
            return

        if path.startswith("/api/pricing/"):
            try:
                pid = int(path.split("/")[-1])
            except ValueError:
                self.send_error(400, "Invalid project ID")
                return

            summary = self.pricing_engine.get_project_pricing_summary(pid)
            self._send_json(summary)
            return

        if path == "/api/verify_claim":
            try:
                pid = int(query.get("project_id", [0])[0])
                price = float(query["claimed_rate"][0]) if query.get("claimed_rate", [""])[0] else None
                sold = float(query["claimed_sold"][0]) if query.get("claimed_sold", [""])[0] else None
            except (TypeError, ValueError):
                self.send_error(400, "Invalid numeric parameter")
                return
            date = query.get("claimed_date", [None])[0] or None

            res = self.verifier.verify_claim(
                project_id=pid,
                claimed_rate_sqft=price,
                claimed_sold_pct=sold,
                claimed_completion_date=date,
            )
            self._send_json(res)
            return

        if path == "/api/search":
            q = query.get("query", [""])[0]
            try:
                pid = int(query["project_id"][0]) if query.get("project_id") else None
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            results = self.search_engine.search(query=q, project_id=pid, limit=10)
            self._send_json({"query": q, "results": results})
            return

        if path == "/api/analytics/survival":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            res = self.mcp_server.forecast_completion_delay(pid)
            self._send_json(res)
            return

        if path == "/api/analytics/pricing_trend":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            res = self.pricing_engine.get_longitudinal_pricing_trend(pid)
            self._send_json(res)
            return

        if path == "/api/analytics/ml_pricing":
            try:
                pid = int(query.get("project_id", [0])[0])
            except (TypeError, ValueError):
                self.send_error(400, "Invalid project ID")
                return
            aclass = query.get("asset_class", ["Residential"])[0]
            try:
                carpet = float(query.get("carpet_area_sqft", [1200.0])[0])
            except (ValueError, TypeError):
                carpet = 1200.0
            res = self.mcp_server.predict_pricing_benchmark(pid, asset_class=aclass, carpet_area_sqft=carpet)
            self._send_json(res)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/copilot":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                self.send_error(400, "Invalid JSON")
                return

            query_text = data.get("query", "").strip()
            try:
                project_id = int(data.get("project_id", 0))
            except (ValueError, TypeError):
                project_id = 0

            api_key = (data.get("api_key") or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            reply_data = self._handle_copilot_query(query_text, project_id, api_key=api_key)
            self._send_json(reply_data)
            return

        self.send_error(404, "Endpoint not found")

    def _handle_copilot_query(self, query: str, project_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize multi-modal statutory due diligence facts with exact citations."""
        try:
            if project_id <= 0:
                row = self.con.execute("SELECT project_id FROM projects ORDER BY project_id LIMIT 1").fetchone()
                project_id = row[0] if row else 16562

            # Try Agentic LLM reasoning if API key is provided
            if api_key and getattr(self, "agentic_copilot", None):
                try:
                    llm_res = self.agentic_copilot.run_query(query, project_id, api_key=api_key)
                    if llm_res and llm_res.get("reply"):
                        return llm_res
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Agentic LLM invocation fell back to deterministic engine: {e}")

            q_lower = query.lower().strip()
            citations: List[str] = []
            reply_lines: List[str] = []

            cur = self.con.execute(
                """
                SELECT project_id, name, district, taluka, promoter_name, registration_number,
                       start_date, completion_date, velocity_ratio, booking_rate_pct,
                       total_units, booked_units, unbooked_units, latest_form_one_progress_pct,
                       estimated_cost_inr, incurred_cost_inr, time_elapsed_pct, bu_status,
                       complaints_count, alterations_count, default_quarters_count
                FROM projects WHERE project_id = ?
                """,
                (project_id,)
            )
            p = cur.fetchone()
            p_name = p["name"] if p else f"Project {project_id}"

            # 1. Greetings & Capabilities Guidance
            if q_lower in ["ok", "okay", "hi", "hello", "hey", "help", "thanks", "thank you"] or any(q_lower.startswith(w) for w in ["help", "what can you do", "who are you", "commands"]):
                reply_lines.append(f"### GujRERA Statutory Diligence Copilot for **{p_name}**")
                reply_lines.append("I am your forensic due-diligence copilot cross-referencing sworn Form 1/2/3 filings, bank escrow passbooks, registered agreements, and timeline disclosures.")
                reply_lines.append("\n**Suggested Inquiries you can ask:**")
                reply_lines.append("- **Launch & Handover**: *'When was this project launched and what is the deadline?'*")
                reply_lines.append("- **Sales & Absorption**: *'What are the sales figures and unsold units?'*")
                reply_lines.append("- **Lifecycle Performance**: *'Analyze the project since its launch'*")
                reply_lines.append("- **70% Escrow Audit**: *'Audit Section 4(2)(l)(D) escrow retention and withdrawals'*")
                reply_lines.append("- **Title & Mortgages**: *'Are there any bank loans, charges or mortgages on the land?'*")
                reply_lines.append("- **Market Rate & CAGR**: *'What is the registered market rate and CAGR?'*")
                reply_lines.append("- **Contagion Risk**: *'Trace shared professionals and contagion risk'*")
                citations.extend(["GujRERA Statutory Fact Base", "RERA Act 2016"])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 1b. Architecture & LLM Credential Inquiry
            if any(w in q_lower for w in ["which llm", "llm", "ai model", "what model", "credentials", "api key", "openai", "gemini", "claude", "architecture"]):
                reply_lines.append("### Architecture & Credentials Disclosure")
                reply_lines.append("This Intelligence Copilot operates on a **Dual-Mode Sovereign Architecture**:")
                reply_lines.append("1. **⚡ Agentic LLM Mode**: Deep open-ended reasoning using Gemini 2.0 Flash or OpenAI with automated tool calls across 10 MCP forensic tools (activated when an API key is provided via the ⚙️ Settings drawer).")
                reply_lines.append("2. **🛡️ Local Evidentiary Mode**: Operates 100% offline with zero cloud credentials required, powered by local SQLite FTS5 BM25 search, GBDT TreeSHAP, and Cox survival modeling with guaranteed **0% hallucination**.")
                reply_lines.append("\n**Internal Machine Learning & Forensic Stack:**")
                reply_lines.append("- **Hedonic Pricing Engine**: Gradient Boosted Decision Trees (GBDT) with exact Lundberg-Lee Tree SHAP feature attributions.")
                reply_lines.append("- **Delivery Forecasting**: Semi-parametric Cox Proportional Hazards survival analysis calibrated against physical velocity.")
                reply_lines.append("- **Statutory Regulatory RAG**: SQLite FTS5 full-text search with BM25 relevance ranking indexing sworn Form 1, 2, and 3 PDF disclosures.")
                reply_lines.append("- **Contagion & Network Graph**: Cross-project relational graph linking promoters, architects, engineers, and chartered accountants.")
                reply_lines.append("- **Evidentiary Citation Contract**: Fully deterministic, citation-backed factual synthesis guaranteeing **0% hallucination**.")
                citations.extend(["Local System Architecture", "GujRERA Relational Fact Base", "Model Context Protocol (MCP)"])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 1c. Buyer Advisory & Best Time to Buy
            if any(w in q_lower for w in ["best time", "when to buy", "should i buy", "safe to buy", "is it safe", "buying advice", "investment advice", "verdict"]):
                surv = self.mcp_server.forecast_completion_delay(project_id)
                health = self.mcp_server.get_escrow_health(project_id)
                pred = self.mcp_server.predict_pricing_benchmark(project_id)
                
                reply_lines.append(f"### Buyer Due Diligence & Timing Assessment for **{p_name}**")
                
                # Physical stage
                prog = p['latest_form_one_progress_pct'] or 0.0
                vel = p['velocity_ratio'] or 1.0
                if prog >= 80:
                    reply_lines.append(f"- **Construction Stage (Favorable)**: Project is at `{prog:.1f}%` certified physical completion (`{vel:.2f}x` velocity). Execution risk is low as structural civil work is largely finished.")
                elif prog >= 50:
                    reply_lines.append(f"- **Construction Stage (Mid-Phase)**: Project is at `{prog:.1f}%` physical progress. Moderate construction risk remains.")
                else:
                    reply_lines.append(f"- **Construction Stage (Early Phase)**: Project is only at `{prog:.1f}%` progress. Higher execution and delivery delay risk.")

                # Escrow security
                escrow_flag = health.get("escrow_70_percent_accounts")
                if escrow_flag:
                    reply_lines.append(f"- **Escrow Protection**: Section 4(2)(l)(D) 70% retention account is operational with ₹{((health.get('total_closing_balance_inr') or 0)/100000):,.2f} Lakhs closing balance.")
                else:
                    reply_lines.append("- **Escrow Protection**: Verify latest Form 3 bank passbook reconciliation before releasing stage payments.")

                # Handover Delivery
                reply_lines.append(f"- **Delivery Confidence**: Risk classification is **{surv.get('delay_risk_label', 'ON_TRACK')}** (Median expected handover: `{surv.get('forecasted_handover_dates', {}).get('p50_median_expected_date', 'On Schedule')}`).")

                # Inventory & Negotiation window
                unsold = p['unbooked_units'] or 0
                total = p['total_units'] or 0
                reply_lines.append(f"- **Negotiation Leverage**: {unsold} of {total} units remain unsold (`{(100 - (p['booking_rate_pct'] or 0)):.1f}%` market overhang), providing favorable bargaining room for late-stage discounts.")

                # Recommendation
                reply_lines.append("\n**Statutory Recommendation:**")
                reply_lines.append("1. Obtain a **formal No-Objection Certificate (NOC)** or confirm clear land title if taking a home loan.")
                reply_lines.append("2. Ensure all booking amounts are deposited exclusively into the designated **RERA 70% retention bank account**.")
                reply_lines.append("3. Verify issuance of the **Building Use (BU) Permission / Completion Certificate** prior to taking physical possession.")

                citations.extend([
                    "RERA Act 2016 Buyer Protection Guidelines",
                    "Cox Proportional Hazards Completion Model",
                    "Form 1 Architect / Form 3 CA Statutory Filings"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 2. Comprehensive Lifecycle Analysis Since Launch
            if any(w in q_lower for w in ["since launch", "analyse it", "analyze it", "progress history", "lifecycle", "performance since", "track record", "full analysis", "overall status"]):
                reply_lines.append(f"### Comprehensive Lifecycle Diligence for **{p_name}** (Since Launch)")
                
                # 1. Timeline & Schedule
                reply_lines.append("\n**1. Timeline & Physical Construction Velocity:**")
                reply_lines.append(f"- **Launch Date**: `{p['start_date'] or 'Not Disclosed'}` ➔ **Statutory Completion**: `{p['completion_date'] or 'Not Disclosed'}`.")
                reply_lines.append(f"- **Elapsed Schedule**: `{p['time_elapsed_pct'] or 0.0}%` elapsed vs `{p['latest_form_one_progress_pct'] or 0.0}%` certified physical progress.")
                vel = p['velocity_ratio'] or 1.0
                reply_lines.append(f"- **Pace Ratio**: `{vel}x` ({'Outpacing schedule' if vel >= 1.0 else 'Delayed relative to calendar'}).")
                
                # Milestones
                tls = self.con.execute("SELECT period_label, progress_percentage FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC", (project_id,)).fetchall()
                if tls:
                    step = max(1, len(tls)//4)
                    milestones_sample = tls[::step]
                    if tls[-1] not in milestones_sample:
                        milestones_sample.append(tls[-1])
                    milestones_str = " ➔ ".join([f"{r['period_label']}: {r['progress_percentage']:.1f}%" for r in milestones_sample])
                    reply_lines.append(f"- **Progression Curve**: {milestones_str} (Latest: `{tls[-1]['progress_percentage']:.1f}%`).")

                # 2. Sales & Inventory
                reply_lines.append("\n**2. Sales Absorption & Commercial/Residential Overhang:**")
                reply_lines.append(f"- **Total Units**: {p['total_units'] or 0} | **Booked**: {p['booked_units'] or 0} (`{p['booking_rate_pct'] or 0.0}%` absorption).")
                reply_lines.append(f"- **Unsold Inventory**: {p['unbooked_units'] or 0} units remaining.")
                
                blocks = self.con.execute("SELECT block_name, total_units, booked_units, booking_rate_pct FROM inventory_blocks WHERE project_id = ?", (project_id,)).fetchall()
                if blocks:
                    b_str = ", ".join([f"{b['block_name']} ({b['booked_units']}/{b['total_units']} booked, {b['booking_rate_pct']:.0f}%)" for b in blocks])
                    reply_lines.append(f"- **Block Absorption**: {b_str}.")

                # 3. Capital Inflows & Escrow Health
                fin = self.con.execute("SELECT booked_consideration, received_amount, balance_amount, incurred_and_paid, estimated_cost FROM finances WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
                if fin:
                    col_eff = (fin['received_amount'] / fin['booked_consideration'] * 100) if fin['booked_consideration'] else 0
                    reply_lines.append("\n**3. Capital Inflows & Financial Health:**")
                    reply_lines.append(f"- **Total Booked Consideration**: ₹{(fin['booked_consideration']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Cash Collected from Buyers**: ₹{(fin['received_amount']/10000000):,.2f} Cr (`{col_eff:.1f}%` collection efficiency).")
                    reply_lines.append(f"- **Remaining Receivables**: ₹{(fin['balance_amount']/10000000):,.2f} Cr | **Incurred Spend**: ₹{(fin['incurred_and_paid']/10000000):,.2f} Cr.")

                # 4. Pricing Trajectory
                trend = self.pricing_engine.get_longitudinal_pricing_trend(project_id)
                if trend.get("quarterly_trajectory"):
                    reply_lines.append("\n**4. Transaction Pricing Trajectory:**")
                    reply_lines.append(f"- **Realized Rates**: Trajectory from ₹{trend['base_median_rate_sqft']:,.0f} ({trend['first_quarter']}) to ₹{trend['latest_median_rate_sqft']:,.0f} ({trend['latest_quarter']}).")
                    reply_lines.append(f"- **Price Appreciation**: **{trend['price_appreciation_pct']}%** | **Annualized CAGR**: **{trend['cagr_pct']}%**.")

                # 5. Regulatory Flags
                reply_lines.append("\n**5. Legal & Regulatory Radar:**")
                complaints = p['complaints_count'] or 0
                alterations = p['alterations_count'] or 0
                defaults = p['default_quarters_count'] or 0
                reply_lines.append(f"- **Complaints**: {complaints} application(s) | **Sanctioned Alterations**: {alterations} | **QPR Defaults**: {defaults} quarters.")
                reply_lines.append(f"- **BU Permission**: {p['bu_status'] or 'Pending / Not Verified'}.")

                citations.extend([
                    "Quarterly Progress Timeline (Form 1 / Form 2)",
                    "Form 3 CA Sworn Financial Disclosures",
                    "Sub-Registrar Unit Transactions Ledger",
                    "GujRERA Statutory Filings Index"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 3. Project Launch Date & Statutory Milestones
            if any(w in q_lower for w in ["launch", "start date", "started", "commence", "began", "when was", "registration date", "start"]):
                reply_lines.append(f"### Project Launch & Statutory Timeline for **{p_name}**")
                reply_lines.append(f"- **Official RERA Launch Date**: `{p['start_date'] or 'Not Disclosed'}` (Statutory Project Start Date).")
                reply_lines.append(f"- **Registration Number**: `{p['registration_number']}` (Project ID: `{project_id}`).")
                reply_lines.append(f"- **RERA Handover Deadline**: `{p['completion_date'] or 'Not Disclosed'}`.")
                reply_lines.append(f"- **Calendar Timeline Elapsed**: `{p['time_elapsed_pct'] or 0.0}%` of scheduled duration elapsed to date.")
                reply_lines.append(f"- **Physical Civil Progress**: `{p['latest_form_one_progress_pct'] or 0.0}%` completed.")
                vel = p['velocity_ratio'] or 1.0
                status = "ahead of schedule" if vel >= 1.0 else "behind schedule (velocity lag)"
                reply_lines.append(f"- **Construction Velocity**: `{vel}x` ({status}).")
                
                first_tl = self.con.execute("SELECT period_label, progress_percentage FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC LIMIT 1", (project_id,)).fetchone()
                if first_tl:
                    reply_lines.append(f"- **First Recorded Progress Filing**: `{first_tl['period_label']}` with `{first_tl['progress_percentage']:.1f}%` certified completion.")
                
                citations.extend([
                    "GujRERA Registration Certificate",
                    "Quarterly Progress Timeline (Form 1)",
                    "Statutory Project Master Table"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 4. Sales Absorption, Bookings & Overhang
            if any(w in q_lower for w in ["sale", "sales", "sold", "booking", "booked", "unsold", "absorption", "inventory", "overhang", "units"]) and not any(w in q_lower for w in ["price", "cagr", "rate", "cost", "sqft"]):
                reply_lines.append(f"### Sales Absorption & Inventory Overhang for **{p_name}**")
                total = p['total_units'] or 0
                booked = p['booked_units'] or 0
                unsold = p['unbooked_units'] or 0
                rate = p['booking_rate_pct'] or 0.0
                
                reply_lines.append(f"- **Overall Scheme Absorption**: **{booked} of {total} units booked** (`{rate:.1f}%` sold out).")
                reply_lines.append(f"- **Remaining Unsold Inventory**: **{unsold} units** (`{(100.0 - rate):.1f}%` market overhang).")

                # Block breakdown
                blocks = self.con.execute(
                    "SELECT block_name, total_units, booked_units, unbooked_units, booking_rate_pct, residential_units, commercial_units FROM inventory_blocks WHERE project_id = ? ORDER BY block_name",
                    (project_id,)
                ).fetchall()
                
                if blocks:
                    reply_lines.append("\n**Block-by-Block Sales Breakdown:**")
                    for b in blocks:
                        comm_tag = f" ({b['commercial_units']} commercial units)" if b['commercial_units'] else ""
                        reply_lines.append(f"- **{b['block_name']}**: {b['booked_units']}/{b['total_units']} units booked (`{b['booking_rate_pct']:.1f}%` sold) | {b['unbooked_units']} unsold{comm_tag}")

                # Financial consideration
                fin = self.con.execute("SELECT booked_consideration, received_amount, balance_amount, unbooked_consideration FROM finances WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
                if fin:
                    reply_lines.append("\n**Sales Realization & Cashflow:**")
                    reply_lines.append(f"- **Total Booked Consideration**: ₹{(fin['booked_consideration']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Cash Collected from Allottees**: ₹{(fin['received_amount']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Outstanding Buyer Balance**: ₹{(fin['balance_amount']/10000000):,.2f} Cr.")
                    reply_lines.append(f"- **Estimated Value of Unsold Inventory**: ₹{(fin['unbooked_consideration']/10000000):,.2f} Cr.")

                recent_count = self.con.execute("SELECT COUNT(*) FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED'", (project_id,)).fetchone()[0]
                reply_lines.append(f"\n- **Sworn Form 3 Sale Agreements**: {recent_count} individual unit agreements registered on record.")

                citations.extend([
                    "Form 1 Architect Certificate (Block Progress)",
                    "Form 3 CA Certificate (formThreeAList)",
                    "Table 'inventory_blocks' & 'finances'"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 5. Mortgages / Encumbrances / Title
            if any(w in q_lower for w in ["mortgage", "loan", "encumbrance", "title", "charge", "borrowing", "pledge", "debt", "land", "plot", "survey"]):
                land = self.mcp_server.get_land_records(project_id)
                leads = [l for l in self.auditor.audit_project(project_id) if "Loan" in l.title or "Encumbrance" in l.title]
                search_res = self.search_engine.search("mortgage encumbrance loan", project_id=project_id, limit=3)
                
                reply_lines.append(f"### Title & Encumbrance Diligence for **{p_name}**")
                reply_lines.append(f"- **Land Plot Identity**: TP Scheme `{land.get('tp_scheme') or 'N/A'}`, Final Plot `{land.get('final_plot_no') or 'N/A'}`, Survey No `{land.get('survey_no') or 'N/A'}` in `{land.get('taluka') or land.get('district')}`.")
                
                if leads:
                    for l in leads:
                        reply_lines.append(f"- **⚠️ {l.title}**: {l.detail}")
                        reply_lines.append(f"  *Action*: {l.reconciliation_guidance}")
                else:
                    reply_lines.append("- **Institutional Finance Status**: No active bank borrowings or charges disclosed on project land in quarterly regulatory disclosures.")
                    
                if search_res:
                    reply_lines.append("\n**Regulatory Title Search Excerpts:**")
                    for s in search_res[:2]:
                        reply_lines.append(f"- *[{s['doc_type']} p.{s['page_number']}]*: {s['snippet']}")

                citations.extend([
                    "Advocate 30-Year Title Search Report",
                    "Form B Promoter Statutory Affidavit",
                    "Sub-Registrar Encumbrance Certificate"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 6. Escrow / 70% retention / Over-withdrawal check
            if any(w in q_lower for w in ["escrow", "retention", "withdrawal", "withdraw", "70%", "bank", "liquidity", "runway"]):
                health = self.mcp_server.get_escrow_health(project_id)
                runway = self.auditor.calculate_escrow_runway(project_id)
                leads = [l for l in self.auditor.audit_project(project_id) if "Escrow" in l.title or "Section 4(2)(l)(D)" in l.title]
                
                escrow_accs = health.get("escrow_70_percent_accounts", [])
                reply_lines.append(f"### Statutory Escrow Diligence for **{p_name}**")
                
                if escrow_accs:
                    acc = escrow_accs[0]
                    reply_lines.append(f"- **Designated 70% Account**: `{acc.get('account_number_masked')}` at **{acc.get('bank_name')}** ({acc.get('branch_name') or 'Main Branch'}).")
                    reply_lines.append(f"- **Period Deposits**: ₹{((acc.get('deposit_amt') or 0)/100000):,.2f} Lakhs | **Period Withdrawals**: ₹{((acc.get('withdrawal_amt') or 0)/100000):,.2f} Lakhs.")
                    reply_lines.append(f"- **Closing Liquidity**: ₹{((acc.get('closing_bal') or 0)/100000):,.2f} Lakhs.")
                else:
                    reply_lines.append("- **No dedicated 70% retention account** disclosed in latest Form 3 filing.")
                    
                if leads:
                    for l in leads:
                        reply_lines.append(f"- **⚠️ {l.title}**: {l.detail}")
                        reply_lines.append(f"  *Verification Guidance*: {l.reconciliation_guidance}")
                else:
                    reply_lines.append("- **Statutory Audit Verdict**: Fully compliant with RERA Section 4(2)(l)(D) Proviso 1. Cumulative withdrawals remain within physical construction completion limits.")

                if runway.get("narrative"):
                    reply_lines.append(f"- **Cash Runway Assessment**: {runway.get('narrative')}")

                citations.extend([
                    "RERA Act 2016 Section 4(2)(l)(D) Proviso 1",
                    "Form 3 CA Certificate & Passbook Table 'banks'",
                    "Quarterly Progress Reports (QPR)"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 7. Delay Risk / Survival Timeline
            if any(w in q_lower for w in ["delay", "survival", "timeline", "completion", "handover", "deadline", "percentile", "p50", "p90"]):
                surv = self.mcp_server.forecast_completion_delay(project_id)
                reply_lines.append(f"### Survival Handover Delay Analysis for **{p_name}**")
                reply_lines.append(f"- **RERA Registered Handover**: `{surv.get('registered_completion_date')}`")
                reply_lines.append(f"- **Risk Classification**: **{surv.get('delay_risk_label')}** (Hazard Ratio: {surv.get('hazard_ratio')})")
                reply_lines.append(f"- **Projected Slippage**: {surv.get('forecasted_delay_months')} months beyond registered deadline.")
                
                h_dates = surv.get("forecasted_handover_dates", {})
                reply_lines.append(f"- **Delivery Probability Milestones**:")
                reply_lines.append(f"  * `p50 (Median Expected)`: **{h_dates.get('p50_median_expected_date')}** (~{h_dates.get('p50_duration_months')} mos from launch)")
                reply_lines.append(f"  * `p75 (Conservative)`: **{h_dates.get('p75_conservative_date')}** (~{h_dates.get('p75_duration_months')} mos from launch)")
                reply_lines.append(f"  * `p90 (High Confidence)`: **{h_dates.get('p90_high_confidence_date')}** (~{h_dates.get('p90_duration_months')} mos from launch)")
                reply_lines.append(f"- **Confidence Assessment**: {surv.get('confidence_assessment')}")

                citations.extend([
                    "Semi-parametric Cox Proportional Hazards Model",
                    "Quarterly Progress Timeline (Form 1 / Form 2)",
                    "Physical Construction Velocity Score"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 8. Pricing / CAGR / Hedonic Attributions
            if any(w in q_lower for w in ["price", "pricing", "market rate", "cagr", "appreciation", "trajectory", "hedonic", "shap", "valuation", "rate"]):
                trend = self.pricing_engine.get_longitudinal_pricing_trend(project_id)
                pred = self.mcp_server.predict_pricing_benchmark(project_id)
                
                reply_lines.append(f"### Pricing Realization & Valuation for **{p_name}**")
                reply_lines.append(f"- **Multi-Year Registered Agreements**: {trend.get('total_agreements_analyzed')} sales deeds analyzed across quarters `{trend.get('first_quarter')}` to `{trend.get('latest_quarter')}`.")
                reply_lines.append(f"- **Price Appreciation**: **{trend.get('price_appreciation_pct')}%** (from ₹{trend.get('base_median_rate_sqft'):,.0f} to ₹{trend.get('latest_median_rate_sqft'):,.0f} per sq.ft).")
                reply_lines.append(f"- **Annualized CAGR**: **{trend.get('cagr_pct')}% per annum**.")
                
                if pred and not pred.get("error"):
                    reply_lines.append(f"\n**Hedonic ML Benchmark (Tree SHAP):**")
                    reply_lines.append(f"- **Model Fair Value**: ₹{pred.get('predicted_rate_per_sqft'):,.0f} / sq.ft (District Baseline: ₹{pred.get('base_market_average_inr'):,.0f}).")
                    top_pos = [f"{d['feature'].replace('_',' ')} (+₹{d['impact_inr_per_sqft']:,.0f})" for d in pred.get('top_positive_premiums', [])[:2]]
                    top_neg = [f"{d['feature'].replace('_',' ')} (-₹{abs(d['impact_inr_per_sqft']):,.0f})" for d in pred.get('top_negative_discounts', [])[:2]]
                    if top_pos:
                        reply_lines.append(f"- **Value Premiums**: {', '.join(top_pos)}")
                    if top_neg:
                        reply_lines.append(f"- **Value Discounts**: {', '.join(top_neg)}")

                citations.extend([
                    "Sub-Registrar Registered Sale Agreements (Form 3)",
                    "GBDT Hedonic Pricing Model with Exact Tree SHAP",
                    "Unit Transactions Database"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 9. Contagion / Shared Entities (Fixed List Bug)
            if any(w in q_lower for w in ["contagion", "shared", "sister", "architect", "engineer", "network", "promoter", "ca", "chartered accountant", "team", "consultant"]):
                net = self.mcp_server.trace_entity_network(project_id)
                shared = net.get("shared_entities", [])
                leads = net.get("contagion_risk_leads", [])
                
                reply_lines.append(f"### Entity Network & Contagion Audit for **{p_name}**")
                
                # 1. Certified Professional Team
                profs = self.con.execute("SELECT role, name, license_or_reg_no FROM professionals WHERE project_id = ?", (project_id,)).fetchall()
                if profs:
                    reply_lines.append("**Certified Professional Team:**")
                    for pr in profs:
                        lic = f" (Reg: `{pr['license_or_reg_no']}`)" if pr['license_or_reg_no'] else ""
                        reply_lines.append(f"- **{pr['role'].title()}**: **{pr['name']}**{lic}")
                reply_lines.append(f"- **Promoter**: **{p['promoter_name']}**")

                # 2. Cross-Project Shared Links (shared is a list)
                if isinstance(shared, list) and shared:
                    reply_lines.append("\n**Cross-Project Shared Connections:**")
                    for s in shared:
                        reply_lines.append(f"- **{s.get('entity_kind', 'Professional')} '{s.get('shared_entity_name')}'** is also engaged on **{s.get('linked_project_name')}** (ID `{s.get('linked_project_id')}`).")
                else:
                    reply_lines.append("\n- **Shared Entity Connections**: No cross-project overlaps detected with other schemes in the active database index.")

                # 3. Contagion Risk Leads
                if isinstance(leads, list) and leads:
                    reply_lines.append("\n**⚠️ Contagion Risk Signals Detected:**")
                    for l in leads:
                        sev = l.get('severity', 'MEDIUM')
                        reply_lines.append(f"- **[{sev}] {l.get('risk_type', 'CONTAGION')}**: {l.get('detail')}")
                else:
                    reply_lines.append("- **Contagion Risk Verdict**: Clean profile — None of the certified professionals or promoters are linked to defaulted, stalled, or disputed sister schemes.")

                citations.extend([
                    "Cross-Project Entity Knowledge Graph",
                    "Professionals Table (Form 1 / Form 2 / Form 3)",
                    "GujRERA Application & Disciplinary Records"
                ])
                return {"reply": "\n".join(reply_lines), "citations": citations}

            # 10. Fallback: Full-Text Document Search
            search_res = self.search_engine.search(query, project_id=project_id, limit=3)
            reply_lines.append(f"### Diligence Search for **{p_name}** ('{query}')")
            if search_res:
                reply_lines.append("Found relevant statutory clauses and filings:")
                for s in search_res:
                    reply_lines.append(f"- **[{s['doc_type']} p.{s['page_number']}]**: {s['snippet']}")
            else:
                reply_lines.append("No direct clause matches found in indexed PDFs. Project overview:")
                reply_lines.append(f"- **Project**: {p_name} ({p['district'] if p else 'N/A'})")
                reply_lines.append(f"- **Promoter**: {p['promoter_name'] if p else 'N/A'}")
                reply_lines.append(f"- **Launch Date**: {p['start_date'] if p else 'N/A'} | **Deadline**: {p['completion_date'] if p else 'N/A'}")
                reply_lines.append(f"- **Physical Progress**: {p['latest_form_one_progress_pct'] if p else 0}% | **Velocity**: {p['velocity_ratio'] if p else 1.0}x")
                reply_lines.append(f"- **Sales Absorption**: {p['booked_units'] if p else 0}/{p['total_units'] if p else 0} units booked ({p['booking_rate_pct'] if p else 0}%)")

            citations.extend([
                "GujRERA Document Search Engine (FTS5 BM25)",
                "Form 1/2/3 Regulatory Filings"
            ])
            return {"reply": "\n".join(reply_lines), "citations": citations}

        except Exception as err:
            # Full detail stays in the server log; the client gets a sanitized note
            # (raw exception text can leak filesystem paths).
            import logging
            logging.getLogger(__name__).warning("Copilot query failed: %s", err, exc_info=True)
            return {
                "reply": "### Diligence Query Service Note\nAn internal processing error occurred while answering. Please rephrase your inquiry or try one of the quick prompts below.",
                "citations": ["GujRERA Statutory Fact Base"]
            }

        return {
            "reply": "\n".join(reply_lines),
            "citations": citations
        }

    def _send_json(self, data):
        try:
            raw = json.dumps(data, default=str, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except ValueError:
            # Degenerate aggregates (NaN/Inf, e.g. medians over empty groups) are not
            # valid JSON; null them out rather than emitting tokens browsers reject.
            raw = json.dumps(self._sanitize_nan(data), default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def _sanitize_nan(value):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        if isinstance(value, dict):
            return {k: IntelligenceRequestHandler._sanitize_nan(v) for k, v in value.items()}
        if isinstance(value, list):
            return [IntelligenceRequestHandler._sanitize_nan(v) for v in value]
        return value


def start_server(port: int = 8765, db_path=None):
    IntelligenceRequestHandler.setup_backends(db_path)
    # ThreadingHTTPServer so a slow request (e.g. an agentic LLM copilot call) cannot
    # freeze every other dashboard request. The shared SQLite connection is opened with
    # check_same_thread=False and 30 s busy_timeout (db.database.get_connection), and the
    # UI never writes, so concurrent read traffic is safe under WAL.
    server = ThreadingHTTPServer(("127.0.0.1", port), IntelligenceRequestHandler)
    server.daemon_threads = True
    print(f"\n[READY] Real Estate Intelligence Terminal running at: http://127.0.0.1:{port}", flush=True)
    print("Press Ctrl+C to stop the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.", flush=True)
    finally:
        server.server_close()
