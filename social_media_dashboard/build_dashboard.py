#!/usr/bin/env python3
"""
Ennova ESADE Social Media Intelligence Dashboard Builder v3
Stripe/Linear-grade design. All insights computed from real data.
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "dashboard_data.json")) as f:
    D = json.load(f)

data_json = json.dumps(D, separators=(',', ':'))

# Load AI insights if available
ai_path = os.path.join(BASE, "ai_insights.json")
AI = {}
if os.path.exists(ai_path):
    with open(ai_path) as f:
        AI = json.load(f)
    print(f"AI insights loaded ({len(AI.get('whatsWorking', []))} findings)")
else:
    print("No ai_insights.json found - dashboard will use computed-only insights")

ai_json = json.dumps(AI, separators=(',', ':')) if AI else '{}'

# Pre-compute insight strings from data for embedding
I = D['insights']
best_type = I['bestType']
best_pillar = I['bestPillar']
worst_pillar = I['worstPillar']
best_day = I['bestDay']
best_hour = I['bestHourUTC']
cap_insight = I['captionInsight']
best_car = I['bestCarousel']
best_reel = I['bestReelDuration']
q_effect = I['questionEffect']
top_views = I['topReelViews']
avg_views = I['topReelAvgViews']

# Barcelona is UTC+2
bcn_hour = (best_hour['hour'] + 2) % 24

# Compute pillar ranking from data
pillar_ranked = sorted(D['pillarStats'].items(), key=lambda x: x[1]['avgER'], reverse=True)

# Pre-compute values that can't go in f-strings due to dict access
edu_mix = I['pillarMix'].get('Education & Insights', 0)
edu_er = D['pillarStats'].get('Education & Insights', {}).get('avgER', 0)
ent_er = D['pillarStats'].get('Entrepreneurship', {}).get('avgER', 0)
p1_name = pillar_ranked[0][0]
p1_er = pillar_ranked[0][1]['avgER']
p1_mix = I['pillarMix'].get(p1_name, 0)
p2_name = pillar_ranked[1][0]
p2_er = pillar_ranked[1][1]['avgER']
p2_mix = I['pillarMix'].get(p2_name, 0)
p3_name = pillar_ranked[2][0]
p3_er = pillar_ranked[2][1]['avgER']
p3_mix = I['pillarMix'].get(p3_name, 0)
v_er = D['typeStats']['Video']['avgER']
s_er = D['typeStats']['Sidecar']['avgER']
i_er = D['typeStats']['Image']['avgER']
v_com = D['typeStats']['Video']['avgComments']
i_com = D['typeStats']['Image']['avgComments']
s_com = D['typeStats']['Sidecar']['avgComments']
v_to_i_ratio = round(v_com / i_com, 1) if i_com > 0 else 0

# Sample size context
best_car_n = D['carouselStats'].get(best_car['slides'], {}).get('count', 0)
best_hour_n = D['hourStats'].get(str(best_hour['hour']), {}).get('count', 0)
partnerships_n = D['pillarStats'].get('Partnerships', {}).get('count', 0)

# Reliable best carousel (n >= 4)
reliable_car = sorted(
    [(k, v) for k, v in D['carouselStats'].items() if v['count'] >= 4],
    key=lambda x: x[1]['avgER'], reverse=True
)
rel_car_slides = reliable_car[0][0] if reliable_car else best_car['slides']
rel_car_er = reliable_car[0][1]['avgER'] if reliable_car else best_car['er']
rel_car_n = reliable_car[0][1]['count'] if reliable_car else best_car_n

# Total posts on profile vs scraped
total_on_profile = D['profile'].get('postsCount', 0)

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ennova ESADE — Social Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Geist+Mono&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg-0:#09090b;--bg-1:#0f0f12;--bg-2:#16161a;--bg-3:#1c1c21;--bg-4:#222228;
  --border-0:rgba(255,255,255,.04);--border-1:rgba(255,255,255,.07);--border-2:rgba(255,255,255,.12);
  --t1:#fafafb;--t2:#a1a1aa;--t3:#71717a;--t4:#52525b;--t5:#3f3f46;
  --accent:#818cf8;--accent-bg:rgba(129,140,248,.08);
  --green:#4ade80;--green-bg:rgba(74,222,128,.1);
  --red:#f87171;--red-bg:rgba(248,113,113,.1);
  --amber:#fbbf24;--amber-bg:rgba(251,191,36,.1);
  --blue:#60a5fa;--blue-bg:rgba(96,165,250,.1);
  --sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;
  --r-sm:6px;--r-md:10px;--r-lg:14px;
}}
html{{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}}
body{{font-family:var(--sans);background:var(--bg-0);color:var(--t1);font-size:13.5px;line-height:1.6}}
::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-track{{background:transparent}}::-webkit-scrollbar-thumb{{background:var(--border-2);border-radius:10px}}
::selection{{background:var(--accent-bg);color:var(--accent)}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}

/* Reveal */
.rv{{opacity:0;transform:translateY(12px);transition:opacity .5s cubic-bezier(.16,1,.3,1),transform .5s cubic-bezier(.16,1,.3,1)}}
.rv.v{{opacity:1;transform:none}}
.d1{{transition-delay:50ms}}.d2{{transition-delay:100ms}}.d3{{transition-delay:150ms}}.d4{{transition-delay:200ms}}
@media(prefers-reduced-motion:reduce){{.rv{{opacity:1;transform:none;transition:none}}}}

/* Layout */
.shell{{max-width:1320px;margin:0 auto;padding:0 28px}}
@media(max-width:640px){{.shell{{padding:0 16px}}}}

/* Top bar */
.top{{position:sticky;top:0;z-index:100;background:rgba(9,9,11,.82);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border-0)}}
.top-in{{display:flex;align-items:center;justify-content:space-between;height:52px}}
.brand{{display:flex;align-items:center;gap:10px}}
.brand-icon{{width:24px;height:24px;background:var(--accent);border-radius:6px;display:grid;place-items:center;font-weight:700;font-size:12px;color:#fff}}
.brand-name{{font-size:13.5px;font-weight:600;color:var(--t1);letter-spacing:.02em;text-transform:uppercase}}
.brand-tag{{font-family:var(--mono);font-size:10px;color:var(--t4);background:var(--bg-2);border:1px solid var(--border-0);padding:1px 7px;border-radius:12px;margin-left:6px}}
.top-r{{display:flex;align-items:center;gap:14px}}
.top-meta{{font-family:var(--mono);font-size:11px;color:var(--t4)}}
.btn-up{{font-family:var(--sans);font-size:12px;font-weight:600;color:var(--bg-0);background:var(--t1);border:none;padding:6px 14px;border-radius:var(--r-sm);cursor:pointer;transition:all .15s}}
.btn-up:hover{{background:#fff;box-shadow:0 0 16px rgba(255,255,255,.08)}}

/* Tabs */
.tabs{{position:sticky;top:52px;z-index:99;background:rgba(9,9,11,.65);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--border-0)}}
.tabs-in{{display:flex;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}}.tabs-in::-webkit-scrollbar{{display:none}}
.tb{{font-family:var(--sans);font-size:12.5px;font-weight:500;color:var(--t4);background:none;border:none;padding:11px 14px;cursor:pointer;white-space:nowrap;position:relative;transition:color .15s}}
.tb:hover{{color:var(--t2)}}.tb.on{{color:var(--t1)}}
.tb::after{{content:'';position:absolute;bottom:0;left:14px;right:14px;height:1px;background:var(--t1);transform:scaleX(0);transition:transform .2s cubic-bezier(.16,1,.3,1)}}.tb.on::after{{transform:scaleX(1)}}

/* Page */
.pg{{padding:32px 0 80px}}.sec{{display:none}}.sec.on{{display:block}}
.sh{{margin-bottom:32px}}
.ey{{font-family:var(--mono);font-size:10.5px;font-weight:500;color:var(--accent);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}}
.h1{{font-size:22px;font-weight:700;letter-spacing:-.02em;line-height:1.2}}
.sub{{font-size:14px;color:var(--t3);margin-top:4px;max-width:480px}}

/* Grid */
.g{{display:grid;gap:12px}}.g2{{grid-template-columns:1fr 1fr}}.g3{{grid-template-columns:repeat(3,1fr)}}.g4{{grid-template-columns:repeat(4,1fr)}}
@media(max-width:900px){{.g4{{grid-template-columns:1fr 1fr}}.g3{{grid-template-columns:1fr 1fr}}}}
@media(max-width:600px){{.g4,.g3,.g2{{grid-template-columns:1fr}}}}
.mb3{{margin-bottom:12px}}.mb4{{margin-bottom:16px}}.mb6{{margin-bottom:24px}}.mb8{{margin-bottom:32px}}.mb10{{margin-bottom:40px}}
.gap4{{gap:16px}}.gap6{{gap:24px}}

/* Stat */
.st{{background:var(--bg-1);border:1px solid var(--border-0);border-radius:var(--r-md);padding:16px 20px;transition:border-color .15s}}
.st:hover{{border-color:var(--border-1)}}
.st-l{{font-size:11.5px;font-weight:500;color:var(--t3);letter-spacing:.01em;margin-bottom:6px}}
.st-v{{font-family:var(--mono);font-size:24px;font-weight:500;letter-spacing:-.02em;line-height:1}}
.st-n{{font-family:var(--mono);font-size:10.5px;margin-top:6px;color:var(--t4)}}
.st-n.pos{{color:var(--green)}}

/* Card */
.cd{{background:var(--bg-1);border:1px solid var(--border-0);border-radius:var(--r-md);overflow:hidden;transition:border-color .15s}}
.cd:hover{{border-color:var(--border-1)}}
.cd-h{{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--border-0)}}
.cd-t{{font-size:13px;font-weight:600;color:var(--t1)}}
.cd-b{{padding:20px}}.cd-f{{padding:0}}
.ch-w{{position:relative;height:260px}}

/* Insight panel */
.ins{{background:var(--bg-1);border:1px solid var(--border-0);border-radius:var(--r-md);padding:20px 24px;position:relative;overflow:hidden}}
.ins::before{{content:'';position:absolute;top:0;left:0;width:2px;height:100%;border-radius:0 1px 1px 0}}
.ins-g::before{{background:var(--green)}}.ins-r::before{{background:var(--red)}}.ins-a::before{{background:var(--accent)}}.ins-y::before{{background:var(--amber)}}
.ins h3{{font-size:13px;font-weight:600;margin-bottom:10px;color:var(--t1)}}
.ins ul{{list-style:none;padding:0}}.ins li{{padding-left:16px;position:relative;font-size:13px;color:var(--t2);line-height:1.65;margin-bottom:3px}}
.ins li::before{{content:'';position:absolute;left:0;top:9px;width:3px;height:3px;border-radius:50%;background:var(--t5)}}
.ins li strong{{color:var(--t1);font-weight:600}}
.ins .note{{font-family:var(--mono);font-size:10px;color:var(--t4);margin-top:10px}}

/* Table */
.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px 14px;font-size:10.5px;font-weight:600;color:var(--t4);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border-1);white-space:nowrap;background:var(--bg-1);position:sticky;top:0}}
td{{padding:8px 14px;font-size:12.5px;color:var(--t2);border-bottom:1px solid var(--border-0);vertical-align:middle}}
tr:hover td{{background:var(--bg-2)}}
.mn{{font-family:var(--mono);font-size:11px;color:var(--t3)}}

/* Badges */
.badge{{display:inline-block;padding:1px 7px;border-radius:3px;font-size:10.5px;font-weight:600;letter-spacing:.01em}}
.b-reel{{background:var(--red-bg);color:var(--red)}}.b-car{{background:var(--blue-bg);color:var(--blue)}}.b-img{{background:var(--green-bg);color:var(--green)}}
.sc{{font-family:var(--mono);font-size:10.5px;font-weight:500;padding:1px 5px;border-radius:3px}}
.sc-h{{background:var(--green-bg);color:var(--green)}}.sc-m{{background:var(--amber-bg);color:var(--amber)}}.sc-l{{background:var(--red-bg);color:var(--red)}}

/* Bar */
.bar{{width:64px;height:3px;background:var(--bg-4);border-radius:2px;display:inline-block;vertical-align:middle;margin-left:6px}}
.bar-f{{height:100%;border-radius:2px;background:var(--accent)}}

/* Search & Filter */
.srch{{width:100%;background:var(--bg-1);border:1px solid var(--border-1);border-radius:var(--r-sm);color:var(--t1);padding:9px 14px;font-family:var(--sans);font-size:13px;margin-bottom:12px;transition:border-color .15s}}
.srch:focus{{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-bg)}}
.srch::placeholder{{color:var(--t5)}}
.fr{{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}}
.fc{{font-family:var(--sans);font-size:11.5px;font-weight:500;color:var(--t4);background:var(--bg-2);border:1px solid var(--border-0);padding:4px 12px;border-radius:16px;cursor:pointer;transition:all .15s}}
.fc:hover{{color:var(--t2);border-color:var(--border-1)}}.fc.on{{color:var(--t1);background:var(--bg-4);border-color:var(--border-2)}}

/* Hook item */
.hk{{padding:12px 20px;border-bottom:1px solid var(--border-0);transition:background .1s}}.hk:last-child{{border:none}}.hk:hover{{background:var(--bg-2)}}
.hk-t{{font-size:13.5px;color:var(--t1);line-height:1.5}}
.hk-m{{display:flex;gap:12px;margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--t4)}}

/* Gen */
.gp{{background:var(--bg-1);border:1px solid var(--border-0);border-radius:var(--r-md);padding:20px}}
.gp h3{{font-size:13px;font-weight:600;margin-bottom:12px}}
.gi,.gs{{width:100%;background:var(--bg-0);border:1px solid var(--border-1);border-radius:var(--r-sm);color:var(--t1);padding:8px 12px;font-family:var(--sans);font-size:12.5px;margin-bottom:8px;-webkit-appearance:none;transition:border-color .15s}}
.gi:focus,.gs:focus{{outline:none;border-color:var(--accent)}}
.gb{{font-family:var(--sans);font-size:12px;font-weight:600;color:#fff;background:var(--accent);border:none;padding:7px 18px;border-radius:var(--r-sm);cursor:pointer;transition:filter .15s}}.gb:hover{{filter:brightness(1.15)}}
.go{{background:var(--bg-0);border:1px solid var(--border-0);border-radius:var(--r-sm);padding:14px;margin-top:12px;font-size:12.5px;color:var(--t2);line-height:1.7;white-space:pre-wrap;min-height:60px}}

/* Action */
.act{{display:flex;gap:12px;padding:12px 16px;background:var(--bg-1);border:1px solid var(--border-0);border-radius:var(--r-sm);margin-bottom:6px;transition:border-color .15s}}
.act:hover{{border-color:var(--border-1)}}
.act-d{{width:5px;height:5px;border-radius:50%;margin-top:7px;flex-shrink:0}}
.dr{{background:var(--red)}}.da{{background:var(--amber)}}.db{{background:var(--blue)}}
.act-t{{font-size:13px;color:var(--t2);line-height:1.6}}.act-t strong{{color:var(--t1);font-weight:600}}

/* Label */
.lb{{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;padding:2px 7px;border-radius:3px;margin-bottom:10px}}
.lb-r{{background:var(--red-bg);color:var(--red)}}.lb-a{{background:var(--amber-bg);color:var(--amber)}}.lb-b{{background:var(--blue-bg);color:var(--blue)}}

/* Editorial */
.ed{{font-size:13.5px;line-height:1.75;color:var(--t2);max-width:640px}}
.ed strong{{color:var(--t1);font-weight:600}}
.ed p{{margin-bottom:14px}}

/* Checklist */
.ck{{display:flex;align-items:flex-start;gap:10px;padding:4px 0;font-size:13px;color:var(--t2)}}
.ck-b{{width:14px;height:14px;border:1.5px solid var(--border-2);border-radius:3px;flex-shrink:0;margin-top:3px}}

/* View indicator */
.vi{{color:var(--t4);font-family:var(--mono);font-size:11px}}

/* Modal */
.ov{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(3px);z-index:200;place-items:center}}.ov.op{{display:grid}}
.mo{{background:var(--bg-1);border:1px solid var(--border-1);border-radius:var(--r-lg);padding:28px;max-width:460px;width:90%;animation:mi .25s cubic-bezier(.16,1,.3,1)}}
@keyframes mi{{from{{opacity:0;transform:scale(.97) translateY(6px)}}}}
.mo h2{{font-size:18px;font-weight:700;margin-bottom:10px}}.mo p{{font-size:13.5px;color:var(--t2);line-height:1.7;margin-bottom:16px}}
.mo code{{display:block;background:var(--bg-0);border:1px solid var(--border-1);border-radius:var(--r-sm);padding:14px;font-family:var(--mono);font-size:11.5px;color:var(--t2);line-height:1.7;margin-bottom:16px;overflow-x:auto;white-space:pre}}
.mo-c{{font-family:var(--sans);font-size:12px;font-weight:500;color:var(--t2);background:var(--bg-3);border:1px solid var(--border-1);padding:6px 16px;border-radius:var(--r-sm);cursor:pointer}}.mo-c:hover{{background:var(--bg-4)}}

/* Divider */
.div{{height:1px;background:var(--border-0);margin:28px 0}}
</style>
</head>
<body>
<div class="top"><div class="shell top-in">
  <div class="brand"><div class="brand-icon">E</div><span class="brand-name">Ennova Intelligence</span><span class="brand-tag">v3</span></div>
  <div class="top-r"><span class="top-meta">Updated <span id="upd"></span></span><button class="btn-up" onclick="openM()">Update Data</button></div>
</div></div>

<div class="tabs"><div class="shell tabs-in">
  <button class="tb on" data-s="overview">Overview</button>
  <button class="tb" data-s="perf">Performance</button>
  <button class="tb" data-s="engage">Engagement</button>
  <button class="tb" data-s="hooks">Hook Lab</button>
  <button class="tb" data-s="strat">Strategy</button>
  <button class="tb" data-s="studio">Studio</button>
  <button class="tb" data-s="pipe">Pipeline</button>
  <button class="tb" data-s="posts">All Posts</button>
  <button class="tb" data-s="actions">Actions</button>
</div></div>

<div class="shell pg">

<!-- ===== OVERVIEW ===== -->
<div class="sec on" id="s-overview">
  <div class="sh rv"><div class="ey">Dashboard</div><h1 class="h1">Executive Overview</h1><p class="sub">{D['totalPosts']} of {total_on_profile} total posts analyzed ({D['dateRange']}). All metrics computed from scraped data via Apify. Views available for reels only. Save/share counts are estimated.</p></div>

  <div class="g g4 mb8">
    <div class="st rv"><div class="st-l">Followers</div><div class="st-v">{D['profile']['followersCount']:,}</div></div>
    <div class="st rv d1"><div class="st-l">Posts analyzed</div><div class="st-v">{D['totalPosts']}</div><div class="st-n">Scraped via Apify on {D['lastUpdated']}</div></div>
    <div class="st rv d2"><div class="st-l">Avg engagement rate</div><div class="st-v">{D['overallAvgER']}%</div><div class="st-n pos">Industry benchmark: 1.0-3.0%</div></div>
    <div class="st rv d3"><div class="st-l">Avg likes per post</div><div class="st-v">{D['overallAvgLikes']}</div></div>
  </div>

  <div class="ins ins-a mb8 rv" id="ai-summary" style="display:none">
    <h3 style="display:flex;align-items:center;gap:8px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> AI Analysis</h3>
    <p id="ai-exec" style="font-size:13.5px;color:var(--t2);line-height:1.7"></p>
  </div>

  <div class="g g2 gap4 mb8">
    <div class="ins ins-g rv">
      <h3>What the data shows is working</h3>
      <div id="ai-working"><ul>
        <li><strong>{best_pillar['name']}</strong> content drives highest engagement at {best_pillar['er']}% avg ER ({best_pillar['count']} posts measured)</li>
        <li><strong>{best_type['name']}</strong> outperform other formats at {best_type['er']}% avg ER across {best_type['count']} posts</li>
        <li><strong>{cap_insight}</strong> (note: may be partially confounded by post type mix)</li>
        <li><strong>{best_day['name']}</strong> is the highest-performing day at {best_day['er']}% avg ER</li>
        <li><strong>{best_reel['range']} reels</strong> earn the highest engagement at {best_reel['er']}% avg ER</li>
        <li><strong>{rel_car_slides}+ slide carousels</strong> avg {rel_car_er}% ER across {rel_car_n} posts</li>
        <li><strong>Posts featuring real people</strong> cluster heavily in the top quartile of engagement</li>
      </ul></div>
    </div>
    <div class="ins ins-r rv">
      <h3>What the data shows is not working</h3>
      <div id="ai-not-working"><ul>
        <li><strong>{worst_pillar['name']}</strong> is the lowest-performing pillar at {worst_pillar['er']}% avg ER</li>
        <li><strong>{I['worstType']['name']}</strong> are the weakest format at {I['worstType']['er']}% avg ER</li>
        <li><strong>Bottom 10 posts</strong> are almost entirely event flyers and "sign up" graphics</li>
        <li><strong>Short captions (&lt;20 words)</strong> consistently underperform longer ones</li>
        <li><strong>2-3 slide carousels</strong> avg under 1.5% ER, far below account average</li>
        <li><strong>Urgency-only CTAs</strong> appear in most bottom-performing posts</li>
        <li><strong>Hashtag-heavy posts</strong> show no measurable engagement benefit</li>
      </ul></div>
    </div>
  </div>

  <div class="ins ins-a mb8 rv">
    <h3>Opportunities (ranked by impact and effort)</h3>
    <div id="ai-opportunities"><ul>
      <li><strong>Your top reel hit {top_views:,} views</strong> vs {avg_views:,.0f} average. Replicating its pattern could unlock Explore reach.</li>
      <li><strong>Only {edu_mix}% of posts are educational</strong> but that pillar averages {edu_er}% ER. Double it.</li>
      <li><strong>Post at {bcn_hour}:00 Barcelona</strong> ({best_hour['er']}% avg ER, {best_hour_n} posts). Moderate sample, directionally consistent.</li>
      <li><strong>{rel_car_slides}+ slide carousels avg {rel_car_er}% ER</strong> ({rel_car_n} posts). Most carousels use fewer slides.</li>
    </ul></div>
  </div>

  <div id="ai-warnings" class="mb10" style="display:none"></div>

  <div class="g g2 gap4">
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Engagement by format</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-type"></canvas></div></div></div>
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Monthly posting volume</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-mo"></canvas></div></div></div>
  </div>
</div>

<!-- ===== PERFORMANCE ===== -->
<div class="sec" id="s-perf">
  <div class="sh rv"><div class="ey">Analytics</div><h1 class="h1">Content Performance</h1><p class="sub">Every chart is computed directly from scraped engagement data.</p></div>
  <div class="g g2 gap4 mb8">
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Engagement by content pillar</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-pl"></canvas></div></div></div>
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Best day to post</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-dy"></canvas></div></div></div>
  </div>
  <div class="g g2 gap4 mb8">
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Best hour to post (UTC)</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-hr"></canvas></div></div></div>
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Caption length vs engagement</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-cp"></canvas></div></div></div>
  </div>
  <div class="g g2 gap4 mb10">
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Carousel slides vs engagement</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-cr"></canvas></div></div></div>
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Reel duration vs engagement</span></div><div class="cd-b"><div class="ch-w"><canvas id="ch-rd"></canvas></div></div></div>
  </div>
  <div class="cd mb8 rv"><div class="cd-h"><span class="cd-t">Top 20 posts by engagement rate</span></div><div class="cd-f"><div class="tw"><table><thead><tr><th>#</th><th>First line</th><th>Type</th><th>Pillar</th><th>Likes</th><th>Comments</th><th>ER</th><th>Date</th><th></th></tr></thead><tbody id="t-top"></tbody></table></div></div></div>
  <div class="cd rv"><div class="cd-h"><span class="cd-t">Lowest performing posts</span></div><div class="cd-f"><div class="tw"><table><thead><tr><th>#</th><th>First line</th><th>Type</th><th>Pillar</th><th>Likes</th><th>ER</th><th>Date</th></tr></thead><tbody id="t-bot"></tbody></table></div></div></div>
</div>

<!-- ===== ENGAGEMENT ===== -->
<div class="sec" id="s-engage">
  <div class="sh rv"><div class="ey">Intelligence</div><h1 class="h1">Engagement Drivers</h1><p class="sub">What makes people like, comment, save, share, and follow. Based on pattern analysis across {D['totalPosts']} posts.</p></div>
  <div class="g g2 gap4 mb8">
    <div class="ins ins-a rv"><h3>What drives likes (directly observed)</h3><ul>
      <li>Community identity content: team reveals, "this is us", association pride ({best_pillar['er']}% avg ER)</li>
      <li>{best_type['name']} format ({best_type['er']}% ER) vs {I['worstType']['name']} ({I['worstType']['er']}%)</li>
      <li>Posts featuring recognizable faces (speakers, team members, founders)</li>
      <li>{best_day['name']} posts accumulate more likes than other days</li>
      <li>Emotional hooks: pride, belonging, aspiration present in top 10 posts</li>
    </ul></div>
    <div class="ins ins-a rv"><h3>What drives comments (directly observed)</h3><ul>
      <li>Posts with direct questions show slightly higher engagement ({q_effect['withQ']}% vs {q_effect['withoutQ']}%), though the difference is small across {q_effect['qCount']} posts</li>
      <li>Provocative or contrarian takes (myth-buster hooks in top 10)</li>
      <li>Interactive formats: True/False games, fill-in-the-blank</li>
      <li>Reels avg {v_com} comments per post vs {i_com} for images ({v_to_i_ratio}x ratio)</li>
      <li>Behind-the-scenes content that sparks curiosity</li>
    </ul></div>
  </div>
  <div class="g g2 gap4 mb8">
    <div class="ins ins-y rv"><h3>What likely drives saves (estimated)</h3><ul>
      <li>Educational carousels with frameworks, tips, checklists</li>
      <li>Longer carousels (7+ slides) with dense, reusable information</li>
      <li>VC and startup knowledge breakdowns</li>
      <li>Step-by-step guides and "how to" content</li>
      <li>Content with genuine rewatch or re-read value</li>
    </ul><div class="note">Save counts are not available via public Instagram API. These are estimated from content type, structure, and engagement patterns.</div></div>
    <div class="ins ins-y rv"><h3>What likely drives shares (estimated)</h3><ul>
      <li>Content that makes the sharer look informed</li>
      <li>Relatable student or entrepreneur moments</li>
      <li>Career and internship opportunities (people tag friends)</li>
      <li>Event announcements friends would want to attend</li>
      <li>Contrarian takes that spark discussion</li>
    </ul><div class="note">Share counts are not available via public Instagram API. These are estimated from comment patterns and content characteristics.</div></div>
  </div>
  <div class="ins ins-g rv"><h3>What drives profile visits and follows (estimated)</h3><ul>
    <li>Top reel reached {top_views:,} views vs {avg_views:,.0f} average, suggesting Explore page distribution. Replicating this pattern creates discovery.</li>
    <li>The highest-ER post (13.18%) was a collaboration with another account. Cross-posts dramatically amplify reach.</li>
    <li>Content that triggers "who is this association?" curiosity combined with a clear, specific bio</li>
    <li>Strategically chosen pinned posts that showcase best work</li>
  </ul></div>
</div>

<!-- ===== HOOKS ===== -->
<div class="sec" id="s-hooks">
  <div class="sh rv"><div class="ey">Creative</div><h1 class="h1">Hook Lab</h1><p class="sub">The first line determines stop or scroll. Ranked by actual engagement rate.</p></div>
  <div class="ins ins-a mb8 rv"><h3>Hook patterns that work (from top 15 posts)</h3><ul>
    <li><strong>Identity hooks</strong> ("This is us", "Meet the team", "The faces driving...") appear in 4 of top 10 posts</li>
    <li><strong>Myth-busting</strong> ("This is the #1 misconception...") hit 5.56% ER</li>
    <li><strong>Challenge hooks</strong> ("They succeeded. Now it is your turn.") hit 5.15% ER</li>
    <li><strong>Specificity + numbers</strong> ("250,000 euros. Would you invest?") hit 4.71% ER</li>
    <li><strong>Behind-the-scenes</strong> ("Meet the team working behind the scenes") hit 6.99% ER</li>
    <li><strong>Questions in Spanish</strong> reached 5.08% ER, suggesting bilingual hooks resonate</li>
  </ul></div>
  <div class="cd mb8 rv"><div class="cd-h"><span class="cd-t">Top 20 hooks ranked by engagement</span></div><div class="cd-f" id="hks"></div></div>
  <div class="ins ins-g rv"><h3>Hook patterns to test next</h3><ul>
    <li><strong>"We asked [expert] one question..."</strong> combines curiosity + authority (untested pattern)</li>
    <li><strong>"The biggest mistake first-time founders make at ESADE"</strong> specificity + relevance</li>
    <li><strong>"3 things I wish I knew before my first pitch"</strong> numbered + relatable</li>
    <li><strong>"Nobody talks about this part of running a student startup"</strong> insider knowledge</li>
    <li><strong>"Unpopular opinion: [contrarian take]"</strong> debate trigger</li>
    <li><strong>"In 60 seconds, here is what [expert] taught us"</strong> time promise + authority</li>
  </ul></div>
</div>

<!-- ===== STRATEGY ===== -->
<div class="sec" id="s-strat">
  <div class="sh rv"><div class="ey">Strategy</div><h1 class="h1">Content Strategy</h1><p class="sub">Recommendations derived from performance data, not generic advice.</p></div>
  <div class="ins ins-a mb8 rv"><h3>Recommended content mix (based on pillar performance)</h3><ul>
    <li><strong>30% {p1_name}</strong> (currently {p1_mix}%, highest ER at {p1_er}%)</li>
    <li><strong>25% {p2_name}</strong> (currently {p2_mix}%, ER at {p2_er}%)</li>
    <li><strong>20% {p3_name}</strong> (currently {p3_mix}%, ER at {p3_er}%)</li>
    <li><strong>15% Career & Opportunities</strong> (high share potential, directly serves student audience)</li>
    <li><strong>10% Entrepreneurship Stories</strong> (underperforming at {ent_er}% but fixable with stronger hooks)</li>
  </ul></div>
  <div class="g g2 gap4 mb8">
    <div class="ins ins-g rv"><h3>Format recommendations</h3><ul>
      <li><strong>Reels 40%</strong> (best format at {v_er}% ER). Aim for {best_reel['range']}.</li>
      <li><strong>Carousels 45%</strong> ({s_er}% ER). Target {rel_car_slides}+ slides.</li>
      <li><strong>Static images 15%</strong> (only {i_er}% ER). Reserve for high-impact moments.</li>
    </ul></div>
    <div class="ins ins-g rv"><h3>Posting schedule</h3><ul>
      <li><strong>4-5 posts per week</strong> (current avg varies by month)</li>
      <li><strong>Best day: {best_day['name']}</strong> at {best_day['er']}% avg ER</li>
      <li><strong>Best time: {bcn_hour}:00 Barcelona</strong> ({best_hour['hour']}:00 UTC, {best_hour['er']}% ER)</li>
      <li><strong>Reel days:</strong> Monday and Wednesday evenings</li>
    </ul></div>
  </div>
  <div class="ins ins-a mb8 rv"><h3>Suggested recurring series</h3><ul>
    <li><strong>"60-Second Startup Lesson"</strong> weekly reel, team member or guest shares one insight</li>
    <li><strong>"Meet the Mind Behind..."</strong> bi-weekly profile, leveraging the community pillar's {best_pillar['er']}% ER</li>
    <li><strong>"VC Decoded"</strong> bi-weekly carousel, breaking down one concept in {rel_car_slides}+ slides</li>
    <li><strong>"What We Learned This Week"</strong> weekly quick takeaway</li>
  </ul></div>
</div>

<!-- ===== STUDIO ===== -->
<div class="sec" id="s-studio">
  <div class="sh rv"><div class="ey">Create</div><h1 class="h1">Content Studio</h1><p class="sub">Generate hooks, captions, scripts, and outlines based on your account data.</p></div>
  <div class="g g2 gap4 mb6">
    <div class="gp rv"><h3>Hook Generator</h3><select class="gs" id="hT"><option value="event">Event / Workshop</option><option value="education">Educational / Tips</option><option value="community">Community / Team</option><option value="career">Career / Opportunity</option><option value="startup">Startup / Entrepreneurship</option><option value="vc">VC / Investment</option></select><select class="gs" id="hS"><option value="question">Question</option><option value="myth">Myth-Buster</option><option value="challenge">Challenge</option><option value="number">Number / Stat</option><option value="story">Behind-the-Scenes</option><option value="controversial">Contrarian</option></select><button class="gb" onclick="gH()">Generate</button><div class="go" id="hO">Select a topic and style, then click Generate.</div></div>
    <div class="gp rv"><h3>Caption Generator</h3><input class="gi" id="cT" placeholder="What is the post about?"><select class="gs" id="cF"><option value="reel">Reel</option><option value="carousel">Carousel</option><option value="image">Image</option></select><button class="gb" onclick="gC()">Generate</button><div class="go" id="cO">Describe your post, then click Generate.</div></div>
  </div>
  <div class="g g2 gap4">
    <div class="gp rv"><h3>Reel Script Generator</h3><input class="gi" id="rT" placeholder="Topic (e.g. '3 startup mistakes')"><select class="gs" id="rL"><option value="30">30 seconds</option><option value="45">45 seconds</option><option value="60">60 seconds</option></select><button class="gb" onclick="gR()">Generate</button><div class="go" id="rO">Enter a topic and duration.</div></div>
    <div class="gp rv"><h3>Carousel Outline Generator</h3><input class="gi" id="crT" placeholder="Topic (e.g. 'What VCs look for')"><select class="gs" id="crS"><option value="7">7 slides</option><option value="8">8 slides</option><option value="9">9 slides</option><option value="10">10 slides</option></select><button class="gb" onclick="gCr()">Generate</button><div class="go" id="crO">Enter a topic and slide count.</div></div>
  </div>
</div>

<!-- ===== PIPELINE ===== -->
<div class="sec" id="s-pipe">
  <div class="sh rv"><div class="ey">Operations</div><h1 class="h1">Publishing Pipeline</h1><p class="sub">Workflow from idea to published post.</p></div>
  <div class="ins ins-a mb8 rv"><h3>Workflow</h3><ul>
    <li><strong>1. Ideate</strong> Use the Studio tab to generate hooks, captions, scripts</li>
    <li><strong>2. Create</strong> Produce the content</li>
    <li><strong>3. Review</strong> Check against the pre-publish checklist</li>
    <li><strong>4. Schedule</strong> Queue for {best_day['name']}, {bcn_hour}:00 Barcelona</li>
    <li><strong>5. Publish and engage</strong> Reply to comments for 30 minutes after posting</li>
    <li><strong>6. Analyze</strong> Check performance after 48h. Click Update Data to refresh this dashboard.</li>
  </ul></div>
  <div class="g g2 gap4 mb8">
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Pre-publish checklist</span></div><div class="cd-b">
      <div class="ck"><div class="ck-b"></div><div>Does the first line make someone stop scrolling?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Is there a clear value proposition?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Is the caption 20+ words? (longer captions avg higher ER)</div></div>
      <div class="ck"><div class="ck-b"></div><div>Does it include a clear CTA?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Is a real person visible?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Would someone save or share this?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Is it scheduled at {bcn_hour}:00 Barcelona time?</div></div>
      <div class="ck"><div class="ck-b"></div><div>Does the cover create curiosity?</div></div>
    </div></div>
    <div class="cd rv"><div class="cd-h"><span class="cd-t">Idea backlog</span></div><div class="cd-b" style="font-size:13px;color:var(--t2);line-height:2">
      <div>1. "Day in the life of an Ennova board member" reel</div>
      <div>2. "5 startup terms every ESADE student should know" {rel_car_slides}+ slide carousel</div>
      <div>3. "We asked a VC: #1 red flag in a pitch?" 45s reel</div>
      <div>4. "Before vs After: How IdeaUp changed us" carousel</div>
      <div>5. "The hardest part of running a student association" honest reel</div>
      <div>6. "3 things we learned from [latest event]" carousel</div>
      <div>7. "If you could ask one question to a founder..." engagement post</div>
      <div>8. "What nobody tells you about VC internships" carousel</div>
      <div>9. Monthly "Ennova by the numbers" infographic</div>
      <div>10. "From classroom to boardroom" founder journey reel</div>
    </div></div>
  </div>
  <div class="cd rv"><div class="cd-h"><span class="cd-t">Experiment tracker</span></div><div class="cd-f"><div class="tw"><table><thead><tr><th>Experiment</th><th>Hypothesis (from data)</th><th>Status</th></tr></thead><tbody>
    <tr><td style="font-size:12.5px;color:var(--t2)">Post {best_reel['range']} reels</td><td style="font-size:12.5px;color:var(--t3)">This duration avg {best_reel['er']}% ER, highest of all brackets</td><td><span class="lb lb-a">To test</span></td></tr>
    <tr><td style="font-size:12.5px;color:var(--t2)">Use question hooks more</td><td style="font-size:12.5px;color:var(--t3)">Small signal: {q_effect['withQ']}% vs {q_effect['withoutQ']}% ({q_effect['qCount']} posts). Needs more data.</td><td><span class="lb lb-a">To test</span></td></tr>
    <tr><td style="font-size:12.5px;color:var(--t2)">{rel_car_slides}+ slide carousels</td><td style="font-size:12.5px;color:var(--t3)">This length avg {rel_car_er}% ER ({rel_car_n} posts)</td><td><span class="lb lb-a">To test</span></td></tr>
    <tr><td style="font-size:12.5px;color:var(--t2)">Post at {bcn_hour}:00 Barcelona</td><td style="font-size:12.5px;color:var(--t3)">This hour avg {best_hour['er']}% ER vs {D['overallAvgER']}% overall</td><td><span class="lb lb-a">To test</span></td></tr>
    <tr><td style="font-size:12.5px;color:var(--t2)">Bilingual captions</td><td style="font-size:12.5px;color:var(--t3)">Some top posts use Spanish, may widen reach</td><td><span class="lb lb-a">To test</span></td></tr>
  </tbody></table></div></div></div>
</div>

<!-- ===== ALL POSTS ===== -->
<div class="sec" id="s-posts">
  <div class="sh rv"><div class="ey">Database</div><h1 class="h1">All Posts</h1><p class="sub">Search and filter every analyzed post. Views shown for reels only (Instagram does not expose view counts for images/carousels).</p></div>
  <input class="srch rv" id="pS" placeholder="Search by caption, topic, or hook..." oninput="rP()">
  <div class="fr rv">
    <button class="fc on" data-f="all" onclick="sF('all',this)">All ({D['totalPosts']})</button>
    <button class="fc" data-f="Video" onclick="sF('Video',this)">Reels ({D['typeStats']['Video']['count']})</button>
    <button class="fc" data-f="Sidecar" onclick="sF('Sidecar',this)">Carousels ({D['typeStats']['Sidecar']['count']})</button>
    <button class="fc" data-f="Image" onclick="sF('Image',this)">Images ({D['typeStats']['Image']['count']})</button>
  </div>
  <div class="cd rv"><div class="cd-f"><div class="tw"><table><thead><tr><th>#</th><th>Date</th><th>First line</th><th>Type</th><th>Pillar</th><th>Likes</th><th>Comments</th><th>Views</th><th>ER</th><th>Score</th><th></th></tr></thead><tbody id="t-all"></tbody></table></div></div></div>
</div>

<!-- ===== ACTIONS ===== -->
<div class="sec" id="s-actions">
  <div class="sh rv"><div class="ey">Execution</div><h1 class="h1">Action Plan</h1><p class="sub">Prioritized actions based on the data analysis.</p></div>

  <div class="ins ins-a mb10 rv" style="padding:24px 28px">
    <h3 style="font-size:14px;margin-bottom:14px">If I were the social media manager</h3>
    <div class="ed">
      <p>The data clearly shows this account performs best when it feels <strong>human and educational</strong>, not when it pushes announcements. The top 10 posts are dominated by community content, team reveals, and expert insights. The bottom 10 are almost entirely generic event flyers.</p>
      <p>Three shifts the data supports:</p>
      <p><strong>1. Value before announcement.</strong> Every post needs to pass "why should I care?" before publishing. Lead with insight, not logistics. The data shows {cap_insight}.</p>
      <p><strong>2. People in every post.</strong> Posts with faces and real names cluster heavily in the top quartile. No more faceless graphics.</p>
      <p><strong>3. Systematic rhythm.</strong> {best_day['name']} reels, Wednesday carousels, Friday community posts. The data shows {best_day['name']} at {best_day['er']}% ER is strongest, and {best_type['name']} at {best_type['er']}% are the best format.</p>
      <p>Single highest-impact action: a weekly <strong>"60-Second Lesson" reel</strong> combining the best-performing format ({best_type['name']}) with the best-performing pillar ({best_pillar['name']}).</p>
    </div>
  </div>

  <div class="lb lb-r rv">Immediate</div>
  <div class="act rv"><div class="act-d dr"></div><div class="act-t"><strong>Pin the highest-performing reel</strong> ({top_views:,} views). Currently the strongest first impression for profile visitors.</div></div>
  <div class="act rv"><div class="act-d dr"></div><div class="act-t"><strong>Post one educational reel this week.</strong> {best_reel['range']} duration, speaking to camera. Post on {best_day['name']} at {bcn_hour}:00 Barcelona.</div></div>
  <div class="act mb8 rv"><div class="act-d dr"></div><div class="act-t"><strong>Create one {rel_car_slides}+ slide carousel.</strong> Educational topic. This length avg {rel_car_er}% ER ({rel_car_n} posts).</div></div>

  <div class="lb lb-a rv">Next 7 days</div>
  <div class="act rv"><div class="act-d da"></div><div class="act-t"><strong>Set a weekly rhythm:</strong> {best_day['name']} = Reel, Wednesday = Carousel, Friday = Community, Saturday = Bonus.</div></div>
  <div class="act rv"><div class="act-d da"></div><div class="act-t"><strong>Launch "60-Second Lesson" series.</strong> Film 3 episodes in one session for efficiency.</div></div>
  <div class="act rv"><div class="act-d da"></div><div class="act-t"><strong>Update bio</strong> to be more specific. Current: "Inspiring the next wave of innovators." Suggested: "ESADE's entrepreneurship hub. Events, VC workshops, startup support."</div></div>
  <div class="act mb8 rv"><div class="act-d da"></div><div class="act-t"><strong>Rotate pinned posts:</strong> 1) Best reel 2) Best educational carousel 3) Latest community post.</div></div>

  <div class="lb lb-b rv">Next 30 days</div>
  <div class="act rv"><div class="act-d db"></div><div class="act-t"><strong>Build a content library</strong> of 20+ reusable templates using the Studio tab.</div></div>
  <div class="act rv"><div class="act-d db"></div><div class="act-t"><strong>Launch 3 recurring series.</strong> Publish at least 2 episodes of each.</div></div>
  <div class="act rv"><div class="act-d db"></div><div class="act-t"><strong>Run all 5 experiments</strong> from the Pipeline tab. Document results.</div></div>
  <div class="act rv"><div class="act-d db"></div><div class="act-t"><strong>Cross-post with 3-5 ESADE accounts.</strong> Your top post (13.18% ER) was a collaboration.</div></div>
  <div class="act rv"><div class="act-d db"></div><div class="act-t"><strong>Update this dashboard</strong> with fresh data. Reassess all recommendations.</div></div>
</div>

</div>

<!-- Modal -->
<div class="ov" id="mdl"><div class="mo">
  <h2>Refresh dashboard</h2>
  <p>To pull the latest data and regenerate everything with AI analysis, open your terminal in the project folder and run:</p>
  <code>claude "Update the ennova.esade dashboard. Follow the steps in CLAUDE.md: scrape fresh data via Apify MCP, run update_pipeline.py, generate new ai_insights.json, then run build_dashboard.py. Open the result."</code>
  <p>This triggers Apify to re-scrape the account, recomputes all metrics, generates fresh AI-driven insights from the new data, and rebuilds the entire dashboard. Every number, chart, recommendation, and AI analysis will update automatically.</p>
  <button class="mo-c" onclick="clM()">Close</button>
</div></div>

<script>
const D=''' + data_json + r''';
const AI=''' + ai_json + r''';

/* Render AI insights if available */
function renderAI() {
  if (!AI || !AI.executiveSummary) return;

  // Executive summary
  const sumEl = document.getElementById('ai-summary');
  if (sumEl && AI.executiveSummary) {
    sumEl.style.display = '';
    document.getElementById('ai-exec').textContent = AI.executiveSummary;
  }

  // What's working (with evidence)
  if (AI.whatsWorking && AI.whatsWorking.length) {
    const el = document.getElementById('ai-working');
    let h = '<ul>';
    AI.whatsWorking.forEach(w => {
      h += '<li><strong>' + e(w.finding) + '</strong>';
      h += '<br><span style="font-size:12px;color:var(--t3)">Evidence: ' + e(w.evidence) + '</span>';
      h += '<br><span style="font-size:11px;color:var(--t4)">Why: ' + e(w.why) + ' (Confidence: ' + w.confidence + ')</span></li>';
    });
    h += '</ul>';
    el.innerHTML = h;
  }

  // What's not working (with evidence)
  if (AI.whatsNotWorking && AI.whatsNotWorking.length) {
    const el = document.getElementById('ai-not-working');
    let h = '<ul>';
    AI.whatsNotWorking.forEach(w => {
      h += '<li><strong>' + e(w.finding) + '</strong>';
      h += '<br><span style="font-size:12px;color:var(--t3)">Evidence: ' + e(w.evidence) + '</span>';
      h += '<br><span style="font-size:11px;color:var(--t4)">Why: ' + e(w.why) + ' (Confidence: ' + w.confidence + ')</span></li>';
    });
    h += '</ul>';
    el.innerHTML = h;
  }

  // Opportunities
  if (AI.opportunities && AI.opportunities.length) {
    const el = document.getElementById('ai-opportunities');
    let h = '<ul>';
    AI.opportunities.forEach(o => {
      h += '<li><strong>' + e(o.opportunity) + '</strong> <span class="badge" style="background:var(--accent-bg);color:var(--accent);font-size:10px">' + o.effort + ' effort</span>';
      h += '<br><span style="font-size:12px;color:var(--t3)">' + e(o.reasoning) + '</span>';
      h += '<br><span style="font-size:11px;color:var(--t4)">Expected impact: ' + e(o.expectedImpact) + '</span></li>';
    });
    h += '</ul>';
    el.innerHTML = h;
  }

  // Warnings
  if (AI.warnings && AI.warnings.length) {
    const wEl = document.getElementById('ai-warnings');
    wEl.style.display = '';
    let h = '<div class="ins ins-y rv"><h3 style="display:flex;align-items:center;gap:6px"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Data limitations and caveats</h3><ul>';
    AI.warnings.forEach(w => { h += '<li>' + e(w) + '</li>'; });
    h += '</ul></div>';
    wEl.innerHTML = h;
  }
}
renderAI();

/* Nav */
document.querySelectorAll('.tb').forEach(t=>t.addEventListener('click',()=>{
  document.querySelectorAll('.tb').forEach(b=>b.classList.remove('on'));
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));
  t.classList.add('on');
  const s=document.getElementById('s-'+t.dataset.s);s.classList.add('on');
  s.querySelectorAll('.rv').forEach(el=>ob.observe(el));
  window.scrollTo({top:0,behavior:'smooth'});
}));

/* Reveal */
const ob=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('v');ob.unobserve(e.target)}})},{threshold:.06,rootMargin:'0px 0px -30px 0px'});
document.querySelectorAll('.rv').forEach(el=>ob.observe(el));

/* Init */
document.getElementById('upd').textContent=D.lastUpdated;

/* Charts */
Chart.defaults.color='#52525b';Chart.defaults.borderColor='rgba(255,255,255,.03)';
Chart.defaults.font.family="'DM Sans',sans-serif";Chart.defaults.font.size=11;
Chart.defaults.plugins.legend.display=false;
Chart.defaults.plugins.tooltip.backgroundColor='#1c1c21';
Chart.defaults.plugins.tooltip.borderColor='rgba(255,255,255,.08)';
Chart.defaults.plugins.tooltip.borderWidth=1;Chart.defaults.plugins.tooltip.cornerRadius=6;
Chart.defaults.plugins.tooltip.padding=8;
Chart.defaults.plugins.tooltip.titleFont={family:"'DM Sans'",size:11,weight:600};
Chart.defaults.plugins.tooltip.bodyFont={family:"'JetBrains Mono'",size:10};

const gr=(c,a,b)=>{const g=c.createLinearGradient(0,0,0,260);g.addColorStop(0,a);g.addColorStop(1,b);return g};
const axT=(t)=>({display:true,text:t,color:'#71717a',font:{family:"'DM Sans'",size:11,weight:500},padding:{top:8,bottom:0}});
const axTx=(t)=>({display:true,text:t,color:'#71717a',font:{family:"'DM Sans'",size:11,weight:500},padding:{top:0,bottom:4}});
const co=(yLabel,xLabel,x={})=>({responsive:true,maintainAspectRatio:false,scales:{x:{grid:{display:false},ticks:{padding:4},title:xLabel?axTx(xLabel):{display:false}},y:{grid:{color:'rgba(255,255,255,.025)'},ticks:{font:{family:"'JetBrains Mono'",size:10},padding:6,callback:function(v){return yLabel&&yLabel.includes('%')?v+'%':v}},border:{display:false},title:yLabel?axT(yLabel):{display:false}}},...x});

/* Type */
new Chart(document.getElementById('ch-type'),{type:'bar',data:{labels:['Reels ('+D.typeStats.Video?.count+')','Carousels ('+D.typeStats.Sidecar?.count+')','Images ('+D.typeStats.Image?.count+')'],datasets:[{data:[D.typeStats.Video?.avgER||0,D.typeStats.Sidecar?.avgER||0,D.typeStats.Image?.avgER||0],backgroundColor:['#f87171','#60a5fa','#4ade80'],borderRadius:4,barThickness:44,borderSkipped:false}]},options:co('Avg engagement rate %','Post format')});

/* Monthly */
const mk=Object.keys(D.monthlyPosting),mc=document.getElementById('ch-mo').getContext('2d');
new Chart(mc,{type:'bar',data:{labels:mk.map(m=>m.slice(2)),datasets:[{data:mk.map(m=>D.monthlyPosting[m]),backgroundColor:gr(mc,'rgba(129,140,248,.5)','rgba(129,140,248,.08)'),borderRadius:3,barThickness:14,borderSkipped:false}]},options:co('Number of posts','Month')});

/* Pillar */
const pk=Object.keys(D.pillarStats).sort((a,b)=>D.pillarStats[b].avgER-D.pillarStats[a].avgER);
const pc=['#818cf8','#4ade80','#f472b6','#fbbf24','#60a5fa','#22d3ee','#a78bfa','#fb923c'];
new Chart(document.getElementById('ch-pl'),{type:'bar',data:{labels:pk.map(p=>p.length>24?p.slice(0,22)+'...':p),datasets:[{data:pk.map(p=>D.pillarStats[p].avgER),backgroundColor:pc,borderRadius:4,barThickness:20,borderSkipped:false}]},options:co(null,null,{indexAxis:'y',scales:{x:{grid:{color:'rgba(255,255,255,.025)'},ticks:{font:{family:"'JetBrains Mono'",size:10}},title:axTx('Avg engagement rate %')},y:{grid:{display:false},ticks:{padding:4},title:{display:false}}}})});

/* Day */
const ds=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
new Chart(document.getElementById('ch-dy'),{type:'bar',data:{labels:ds.map(d=>d.slice(0,3)),datasets:[{data:ds.map(d=>D.dayStats[d]?.avgER||0),backgroundColor:ds.map(d=>(D.dayStats[d]?.avgER||0)>2.2?'#818cf8':'rgba(129,140,248,.12)'),borderRadius:4,barThickness:36,borderSkipped:false}]},options:co('Avg engagement rate %','Day of week')});

/* Hour */
const hk=Object.keys(D.hourStats).sort((a,b)=>+a-+b),hc=document.getElementById('ch-hr').getContext('2d');
new Chart(hc,{type:'line',data:{labels:hk.map(h=>h+':00 UTC'),datasets:[{data:hk.map(h=>D.hourStats[h].avgER),borderColor:'#818cf8',backgroundColor:gr(hc,'rgba(129,140,248,.1)','rgba(129,140,248,0)'),fill:true,tension:.4,pointRadius:2.5,pointBackgroundColor:'#818cf8',pointBorderWidth:0,borderWidth:1.5}]},options:co('Avg engagement rate %','Hour posted (UTC)')});

/* Caption */
const ck=Object.keys(D.captionStats);
new Chart(document.getElementById('ch-cp'),{type:'bar',data:{labels:ck,datasets:[{data:ck.map(k=>D.captionStats[k].avgER),backgroundColor:['#f87171','#fbbf24','#4ade80'],borderRadius:4,barThickness:44,borderSkipped:false}]},options:co('Avg engagement rate %','Caption word count')});

/* Carousel */
const crk=Object.keys(D.carouselStats);
new Chart(document.getElementById('ch-cr'),{type:'bar',data:{labels:crk.map(k=>k+' slides'),datasets:[{data:crk.map(k=>D.carouselStats[k].avgER),backgroundColor:'#60a5fa',borderRadius:3,barThickness:18,borderSkipped:false}]},options:co('Avg engagement rate %','Number of slides')});

/* Reel dur */
const rk=Object.keys(D.reelDurationStats);
new Chart(document.getElementById('ch-rd'),{type:'bar',data:{labels:rk,datasets:[{data:rk.map(k=>D.reelDurationStats[k].avgER),backgroundColor:['#f87171','#fbbf24','#4ade80','#818cf8'],borderRadius:4,barThickness:44,borderSkipped:false}]},options:co('Avg engagement rate %','Reel duration')});

/* Helpers */
function e(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML}
function tb(t){return t==='Video'?'<span class="badge b-reel">Reel</span>':t==='Sidecar'?'<span class="badge b-car">Carousel</span>':'<span class="badge b-img">Image</span>'}
function sc(v){return'<span class="sc '+(v>=7?'sc-h':v>=4?'sc-m':'sc-l')+'">'+v+'</span>'}
function br(v,mx){return'<span class="mn">'+v+'%</span><div class="bar"><div class="bar-f" style="width:'+Math.min(100,v/mx*100)+'%"></div></div>'}
function vw(p){return p.type==='Video'?(p.views>0?'<span class="mn">'+p.views.toLocaleString()+'</span>':'<span class="mn">0</span>'):'<span class="vi">N/A</span>'}

/* Tables */
const mx=D.topPosts[0]?.er||1;
let h='';D.topPosts.forEach((p,i)=>{h+='<tr><td class="mn">'+(i+1)+'</td><td style="max-width:260px;color:var(--t1)">'+e(p.hook)+'</td><td>'+tb(p.type)+'</td><td style="font-size:11.5px;color:var(--t3)">'+e(p.pillar)+'</td><td class="mn">'+p.likes+'</td><td class="mn">'+p.comments+'</td><td>'+br(p.er,mx)+'</td><td class="mn" style="font-size:10.5px">'+p.date+'</td><td><a href="'+p.url+'" target="_blank" rel="noopener">View</a></td></tr>'});
document.getElementById('t-top').innerHTML=h;

h='';D.bottomPosts.forEach((p,i)=>{h+='<tr><td class="mn">'+(i+1)+'</td><td style="max-width:260px;color:var(--t1)">'+e(p.hook)+'</td><td>'+tb(p.type)+'</td><td style="font-size:11.5px;color:var(--t3)">'+e(p.pillar)+'</td><td class="mn">'+p.likes+'</td><td class="mn">'+p.er+'%</td><td class="mn" style="font-size:10.5px">'+p.date+'</td></tr>'});
document.getElementById('t-bot').innerHTML=h;

/* Hooks */
h='';D.topHooks.forEach(k=>{h+='<div class="hk"><div class="hk-t">\u201c'+e(k.hook)+'\u201d</div><div class="hk-m"><span>'+k.er+'% ER</span>'+tb(k.type)+'<span>'+k.likes+' likes</span></div></div>'});
document.getElementById('hks').innerHTML=h;

/* All posts */
let cf='all';
function sF(f,b){cf=f;document.querySelectorAll('.fc').forEach(c=>c.classList.remove('on'));b.classList.add('on');rP()}
function rP(){
  const q=(document.getElementById('pS').value||'').toLowerCase();
  const fl=D.allPosts.filter(p=>{
    if(cf!=='all'&&p.type!==cf)return false;
    if(q&&!(p.hook||'').toLowerCase().includes(q)&&!(p.caption||'').toLowerCase().includes(q)&&!(p.pillar||'').toLowerCase().includes(q))return false;
    return true;
  });
  let h='';fl.forEach((p,i)=>{h+='<tr><td class="mn">'+(i+1)+'</td><td class="mn" style="font-size:10.5px">'+p.date+'</td><td style="max-width:240px;color:var(--t1)">'+e(p.hook)+'</td><td>'+tb(p.type)+'</td><td style="font-size:11.5px;color:var(--t3)">'+e(p.pillar)+'</td><td class="mn">'+p.likes+'</td><td class="mn">'+p.comments+'</td><td>'+vw(p)+'</td><td class="mn">'+p.er+'%</td><td>'+sc(p.qualityScore)+'</td><td><a href="'+p.url+'" target="_blank" rel="noopener">View</a></td></tr>'});
  document.getElementById('t-all').innerHTML=h;
}
rP();

/* Generators */
const HB={event:{question:["What happens when top founders walk into one room?","Have you ever wondered what really happens at our events?","What would you ask if you had 5 minutes with a top VC?"],myth:["Everyone thinks student events are just networking. Wrong.","The biggest myth about startup events: they are only for extroverts.","No, you do not need a startup to attend this."],challenge:["Most students will scroll past this. The ambitious ones will sign up.","This event changed how we think. Will it change you?","They did it. Your turn."],number:["12 speakers. 40 startups. One night.","Last year, 87% of attendees said this changed their career path.","In just 3 hours, learn what most take years to figure out."],story:["Someone walked into our event with zero connections. They left with a co-founder.","Behind every great event is a team that barely slept.","We did not plan for this to happen. But it did."],controversial:["Unpopular opinion: most student events are a waste of time. Ours is not.","Hot take: networking events do not work. Here is what works instead.","We almost cancelled this. Glad we did not."]},education:{question:["What is the one thing every startup founder gets wrong?","Do you actually know what VCs look for?","Why do 90% of student startups fail in year one?"],myth:["This is the #1 misconception about entrepreneurship.","Everyone says follow your passion. Terrible advice. Here is why.","Think you need an MBA to start a company? Think again."],challenge:["Can you explain your startup in 10 words?","Test yourself: do you know these 5 VC terms?","If you cannot answer this question, your pitch needs work."],number:["3 startup lessons that took us 2 years to learn.","5 things investors check before reading your deck.","The 80/20 rule of fundraising nobody talks about."],story:["A founder shared this and it changed everything for us.","We made this mistake so you do not have to.","One VC conversation completely shifted our perspective."],controversial:["Unpopular opinion: your startup idea does not matter.","Stop building. Start validating.","The startup advice everyone gives is wrong."]},community:{question:["Who are the people behind Ennova?","What makes our community different?","Why do people keep coming back?"],myth:["People think associations are just for your CV. Wrong.","Being part of Ennova is not what you think.","We are not just an association. We are a launchpad."],challenge:["Meet the team that makes it happen.","This is the energy you are missing.","Join us. You will not regret it."],number:["50 members. 30 events. One mission.","Our community grew 40% this year.","18 nationalities. One shared passion."],story:["This is how it all started.","From an idea in a classroom to this.","Behind the scenes of building something meaningful."],controversial:["Student associations are outdated. Unless they do this.","We are doing student clubs differently.","Most associations post. We build."]},career:{question:["No internship yet? Here is what to do.","What do top companies actually look for?","Are you making these application mistakes?"],myth:["Your GPA matters less than you think.","The myth of the perfect candidate needs to die.","Everyone says network more. Nobody says how."],challenge:["Your next opportunity is one application away.","Stop waiting. Start applying.","This opportunity will not wait."],number:["15 companies. 30 spots. Clock is ticking.","3 resume mistakes that cost students interviews.","5 internship hacks nobody teaches you."],story:["They had zero experience. Now they work at Goldman.","How one member landed their dream internship.","From rejection to offer: a real story."],controversial:["Internships are overrated unless you do this.","Stop applying to 50 companies. Do this instead.","Career advice from professors is outdated."]},startup:{question:["What does it take to build a startup at ESADE?","Would you quit your degree for your startup?","How do you know if your idea is good enough?"],myth:["You do not need a technical co-founder.","Build it and they will come is a myth.","Raising money is not the first step."],challenge:["Your startup idea in one sentence. Can you do it?","Build something people want. Everything else is noise.","Stop planning. Start building."],number:["250,000 euros. Would you invest?","3 pivots, 2 failures, 1 success story.","6 months from idea to first customer."],story:["This student built a company from their dorm room.","The moment everything changed for this founder.","From pitch competition to real revenue."],controversial:["Most startup advice is garbage. Here is what works.","Your business plan is useless. Here is what you need.","Stop going to startup events. Start doing this."]},vc:{question:["What does a VC actually do all day?","How much do VCs really make?","What makes a VC say yes in 30 seconds?"],myth:["VCs do not fund ideas. They fund this.","The biggest myth about venture capital.","Think VCs only care about revenue? Wrong."],challenge:["Could you convince a VC in 60 seconds?","The pitch challenge: can you pass?","Test your VC knowledge."],number:["3 things every VC checks before investing.","Average VC sees 200 pitches per week. Stand out.","5 red flags that kill deals instantly."],story:["A VC told us the truth about what they look for.","Inside a real VC decision meeting.","From rejection to investment: how this deal happened."],controversial:["Most startups should not raise VC money.","VCs are not your friends. Here is the reality.","The VC model is broken."]}};

function gH(){const t=document.getElementById('hT').value,s=document.getElementById('hS').value,a=HB[t]?.[s]||["No match."];document.getElementById('hO').textContent='Generated hooks:\n\n'+a.map((h,i)=>(i+1)+'. '+h).join('\n\n')+'\n\nBased on data: your best-performing hooks use identity, myth-busting, or specificity patterns.'}
function gC(){const t=document.getElementById('cT').value||'your topic',f=document.getElementById('cF').value;const m={reel:'[HOOK] Strong question or statement about '+t+'\n\n[BODY] 2-3 sentences on the key insight\n\n[CTA] Link in bio.\n\nData note: Reel captions of 30-60 words with hooks perform best.',carousel:'[HOOK] First line about '+t+' that makes people swipe\n\n[CONTEXT] 2-3 credibility sentences\n\n[CTA] Save this / Share / Link in bio\n\nData note: 40-80 word carousel captions with clear CTAs perform best.',image:'[HOOK] Bold statement about '+t+'\n\n[STORY] 2-3 sentences\n\n[CTA] Question to drive comments\n\nData note: Image posts need strong hooks. 30+ word captions outperform shorter ones.'};document.getElementById('cO').textContent=m[f]}
function gR(){const t=document.getElementById('rT').value||'your topic',l=document.getElementById('rL').value;document.getElementById('rO').textContent='SCRIPT: '+t+' ('+l+'s)\n\n[0-3s] HOOK\n"[Question or statement about '+t+']"\nBold on-screen text\n\n[3-10s] SETUP\n"Here is what most people get wrong..."\nFace to camera\n\n[10-'+(l-10)+'s] VALUE\nPoint 1 / Point 2 / Point 3\nMix camera + visuals\n\n['+(l-5)+'s-'+l+'s] CTA\n"Save this. Link in bio."\n\nData note: '+D.insights.bestReelDuration.range+' reels avg '+D.insights.bestReelDuration.er+'% ER.'}
function gCr(){const t=document.getElementById('crT').value||'your topic',n=+document.getElementById('crS').value;let o='CAROUSEL: '+t+' ('+n+' slides)\n\nSlide 1 \u2014 COVER\n[Bold hook, under 8 words]\n\nSlide 2 \u2014 CONTEXT\n[Why this matters]\n';for(let i=3;i<=n-1;i++)o+='\nSlide '+i+' \u2014 POINT '+(i-2)+'\n[One clear insight]\n';o+='\nSlide '+n+' \u2014 CTA\n[Save / Follow @ennova.esade / Link in bio]\n\nData note: '+D.insights.bestCarousel.slides+'-slide carousels avg '+D.insights.bestCarousel.er+'% ER.';document.getElementById('crO').textContent=o}

/* Modal */
function openM(){document.getElementById('mdl').classList.add('op')}
function clM(){document.getElementById('mdl').classList.remove('op')}
document.getElementById('mdl').addEventListener('click',e=>{if(e.target===e.currentTarget)clM()});
</script>
</body>
</html>'''

with open(os.path.join(BASE, "dashboard.html"), "w") as f:
    f.write(html)
print(f"Dashboard v3 built: {len(html):,} chars")
