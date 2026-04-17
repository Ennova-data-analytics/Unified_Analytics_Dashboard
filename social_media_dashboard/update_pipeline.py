#!/usr/bin/env python3
"""
Ennova ESADE Dashboard — Data Processing & Analysis Pipeline
Called by Claude Code after Apify scraping is complete.

Usage (called automatically by the update workflow):
  python3 update_pipeline.py

Expects these files to already exist (produced by Apify scrape):
  - all_posts.json  (scraped posts)
  - all_reels.json  (scraped reels)
  - profile_data.json (scraped profile)

Produces:
  - processed_data.json (cleaned + scored posts)
  - dashboard_data.json (aggregated analytics for dashboard)
"""

import json
import re
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

def load_json(name):
    path = os.path.join(BASE, name)
    if not os.path.exists(path):
        print(f"ERROR: {name} not found. Run Apify scrape first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)

def save_json(name, data):
    with open(os.path.join(BASE, name), 'w') as f:
        json.dump(data, f, indent=2)

def process_posts():
    """Process raw scraped data into analyzed, scored posts."""
    posts_raw = load_json("all_posts.json")
    reels_raw = load_json("all_reels.json")
    profile = load_json("profile_data.json")

    followers = profile['followersCount']
    print(f"Processing data for @{profile['username']} ({followers:,} followers)")

    # Merge reels not already in posts
    post_ids = {p['id'] for p in posts_raw}
    for r in reels_raw:
        if r['id'] not in post_ids:
            posts_raw.append(r)

    print(f"Total unique content pieces: {len(posts_raw)}")

    processed = []
    for p in posts_raw:
        post = {}
        post['id'] = p.get('id')
        post['shortCode'] = p.get('shortCode')
        post['url'] = p.get('url')
        post['type'] = p.get('type', 'Unknown')
        post['timestamp'] = p.get('timestamp', '')
        post['date'] = post['timestamp'][:10] if post['timestamp'] else ''

        try:
            dt = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
            post['dayOfWeek'] = dt.strftime('%A')
            post['hour'] = dt.hour
            post['month'] = dt.strftime('%Y-%m')
        except:
            post['dayOfWeek'] = ''
            post['hour'] = -1
            post['month'] = ''

        caption = p.get('caption') or ''
        post['caption'] = caption
        post['captionLength'] = len(caption)
        post['captionWords'] = len(caption.split())

        hashtags = re.findall(r'#(\w+)', caption)
        post['hashtags'] = hashtags
        post['hashtagCount'] = len(hashtags)

        mentions = re.findall(r'@([\w.]+)', caption)
        post['mentions'] = mentions
        post['mentionCount'] = len(mentions)

        lines = [l.strip() for l in caption.split('\n') if l.strip()]
        post['hook'] = lines[0] if lines else ''
        post['hookLength'] = len(post['hook'])
        post['cta'] = lines[-1] if len(lines) > 1 else ''

        likes = max(0, p.get('likesCount') or 0)
        comments = p.get('commentsCount') or 0
        views = p.get('videoViewCount') or p.get('videoPlayCount') or 0
        duration = p.get('videoDuration') or 0

        post['likes'] = likes
        post['comments'] = comments
        post['views'] = views
        post['videoDuration'] = duration
        post['locationName'] = p.get('locationName') or ''
        post['isPinned'] = p.get('isPinned') or False
        post['tagged'] = [t.get('username', '') for t in (p.get('taggedUsers') or [])]
        post['taggedCount'] = len(post['tagged'])

        children = p.get('childPosts') or []
        post['carouselLength'] = len(children) if post['type'] == 'Sidecar' else 0

        # Engagement metrics
        post['engagementRate'] = round((likes + comments) / followers * 100, 2) if followers else 0
        post['commentRate'] = round(comments / followers * 100, 3) if followers else 0
        post['likeToCommentRatio'] = round(likes / comments, 1) if comments > 0 else 0

        if views > 0:
            post['viewEngagementRate'] = round((likes + comments) / views * 100, 2)
            post['viewToFollowerRatio'] = round(views / followers * 100, 1)
        else:
            post['viewEngagementRate'] = 0
            post['viewToFollowerRatio'] = 0

        # Content classification
        caption_lower = caption.lower()
        topics = []
        if any(w in caption_lower for w in ['event', 'gala', 'workshop', 'session', 'talk', 'conference', 'summit']):
            topics.append('Event')
        if any(w in caption_lower for w in ['startup', 'entrepreneur', 'founder', 'venture', 'pitch', 'invest']):
            topics.append('Entrepreneurship')
        if any(w in caption_lower for w in ['learn', 'lesson', 'tip', 'how to', 'guide', 'mistake', 'error']):
            topics.append('Educational')
        if any(w in caption_lower for w in ['team', 'member', 'board', 'president', 'meet', 'association']):
            topics.append('Community')
        if any(w in caption_lower for w in ['partner', 'sponsor', 'collab', 'together']):
            topics.append('Partnership')
        if any(w in caption_lower for w in ['apply', 'register', 'sign up', 'link in bio', 'join']):
            topics.append('CTA/Promo')
        if any(w in caption_lower for w in ['thank', 'recap', 'amazing', 'incredible', 'what a']):
            topics.append('Recap/Thanks')
        if any(w in caption_lower for w in ['coming soon', 'announcement', 'excited', 'launching', 'new']):
            topics.append('Announcement')
        if any(w in caption_lower for w in ['internship', 'career', 'job', 'talent', 'opportunity']):
            topics.append('Career')
        if any(w in caption_lower for w in ['vc', 'investor', 'fund', 'capital', 'valuation']):
            topics.append('VC/Finance')
        if not topics:
            topics.append('General')
        post['topics'] = topics
        post['primaryTopic'] = topics[0]

        if 'Event' in topics or 'Recap/Thanks' in topics:
            post['pillar'] = 'Events & Experiences'
        elif 'Educational' in topics or 'VC/Finance' in topics:
            post['pillar'] = 'Education & Insights'
        elif 'Community' in topics:
            post['pillar'] = 'Community & Culture'
        elif 'Career' in topics:
            post['pillar'] = 'Career & Opportunities'
        elif 'Entrepreneurship' in topics:
            post['pillar'] = 'Entrepreneurship'
        elif 'Partnership' in topics:
            post['pillar'] = 'Partnerships'
        elif 'Announcement' in topics or 'CTA/Promo' in topics:
            post['pillar'] = 'Announcements & CTAs'
        else:
            post['pillar'] = 'Brand & General'

        has_link_cta = 'link in bio' in caption_lower
        has_question = '?' in caption
        has_emoji_hook = bool(re.match(r'^[^\w\s]', post['hook'])) if post['hook'] else False

        post['hasLinkCTA'] = has_link_cta
        post['hasQuestion'] = has_question
        post['hasEmojiHook'] = has_emoji_hook

        # Scoring
        hook_score = 5
        if post['hookLength'] > 10: hook_score += 1
        if has_emoji_hook: hook_score += 0.5
        if has_question and post['hook'].endswith('?'): hook_score += 1.5
        if any(w in post['hook'].lower() for w in ['you', 'your', 'we']): hook_score += 1
        if post['hookLength'] > 50: hook_score -= 1
        if any(w in post['hook'].lower() for w in ['what if', 'imagine', 'how', 'why', 'secret', 'truth']): hook_score += 1
        post['hookScore'] = min(10, max(0, round(hook_score, 1)))

        cta_score = 3
        if has_link_cta: cta_score += 2
        if 'sign up' in caption_lower or 'register' in caption_lower: cta_score += 2
        if 'comment' in caption_lower or 'tag' in caption_lower or 'share' in caption_lower: cta_score += 1.5
        if has_question: cta_score += 1
        post['ctaScore'] = min(10, max(0, round(cta_score, 1)))

        save_score = 3
        if 'Educational' in topics: save_score += 2
        if post['type'] == 'Sidecar': save_score += 1.5
        if any(w in caption_lower for w in ['tip', 'lesson', 'step', 'guide', 'framework', 'checklist']): save_score += 2
        if any(w in caption_lower for w in ['mistake', 'avoid', "don't"]): save_score += 1
        if post['carouselLength'] > 5: save_score += 1
        post['saveLikelihood'] = min(10, max(0, round(save_score, 1)))

        share_score = 3
        if any(w in caption_lower for w in ['relatable', 'real', 'honest', 'truth']): share_score += 2
        if 'Community' in topics: share_score += 1
        if post['likes'] > 50: share_score += 1
        if has_question: share_score += 1
        if any(w in caption_lower for w in ['tag', 'share', 'send']): share_score += 1.5
        post['shareLikelihood'] = min(10, max(0, round(share_score, 1)))

        quality = (post['engagementRate'] * 2 + post['hookScore'] + post['ctaScore'] + post['saveLikelihood']) / 5
        post['qualityScore'] = min(10, max(0, round(quality, 1)))

        processed.append(post)

    processed.sort(key=lambda x: x['timestamp'], reverse=True)
    save_json("processed_data.json", processed)
    print(f"Processed {len(processed)} posts -> processed_data.json")
    return processed, profile


def build_analytics(data, profile):
    """Build aggregated analytics from processed data."""
    followers = profile['followersCount']

    # Type stats
    by_type = defaultdict(list)
    for p in data: by_type[p['type']].append(p)
    type_stats = {}
    for t, posts in by_type.items():
        views_posts = [p for p in posts if p['views'] > 0]
        type_stats[t] = {
            'count': len(posts),
            'avgLikes': round(sum(p['likes'] for p in posts)/len(posts), 1),
            'avgComments': round(sum(p['comments'] for p in posts)/len(posts), 1),
            'avgER': round(sum(p['engagementRate'] for p in posts)/len(posts), 2),
            'avgViews': round(sum(p['views'] for p in views_posts)/len(views_posts), 0) if views_posts else 0
        }

    # Pillar stats
    by_pillar = defaultdict(list)
    for p in data: by_pillar[p['pillar']].append(p)
    pillar_stats = {}
    for pillar, posts in by_pillar.items():
        pillar_stats[pillar] = {
            'count': len(posts),
            'avgLikes': round(sum(p['likes'] for p in posts)/len(posts), 1),
            'avgComments': round(sum(p['comments'] for p in posts)/len(posts), 1),
            'avgER': round(sum(p['engagementRate'] for p in posts)/len(posts), 2)
        }

    # Day stats
    by_day = defaultdict(list)
    for p in data:
        if p['dayOfWeek']: by_day[p['dayOfWeek']].append(p)
    day_stats = {}
    for day in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']:
        if day in by_day:
            posts = by_day[day]
            day_stats[day] = {'count': len(posts), 'avgER': round(sum(p['engagementRate'] for p in posts)/len(posts), 2)}

    # Hour stats
    by_hour = defaultdict(list)
    for p in data:
        if p['hour'] >= 0: by_hour[p['hour']].append(p)
    hour_stats = {}
    for h in sorted(by_hour.keys()):
        posts = by_hour[h]
        if len(posts) >= 2:
            hour_stats[str(h)] = {'count': len(posts), 'avgER': round(sum(p['engagementRate'] for p in posts)/len(posts), 2)}

    # Monthly
    monthly = dict(sorted(Counter(p['month'] for p in data if p['month']).items()))

    # Caption length
    caption_stats = {}
    for label, lo, hi in [('Short (<20 words)', 0, 20), ('Medium (20-60)', 20, 60), ('Long (60+)', 60, 9999)]:
        group = [p for p in data if lo <= p['captionWords'] < hi]
        if group:
            caption_stats[label] = {'count': len(group), 'avgER': round(sum(p['engagementRate'] for p in group)/len(group), 2)}

    # Carousel length
    carousel_stats = {}
    by_len = defaultdict(list)
    for p in data:
        if p['type'] == 'Sidecar' and p['carouselLength'] > 0:
            by_len[p['carouselLength']].append(p)
    for length in sorted(by_len.keys()):
        posts = by_len[length]
        carousel_stats[str(length)] = {'count': len(posts), 'avgER': round(sum(p['engagementRate'] for p in posts)/len(posts), 2)}

    # Reel duration
    reel_stats = {}
    vids = [p for p in data if p['type'] == 'Video' and p['videoDuration'] > 0]
    for label, lo, hi in [('0-15s',0,15),('15-30s',15,30),('30-60s',30,60),('60s+',60,999)]:
        group = [p for p in vids if lo <= p['videoDuration'] < hi]
        if group:
            reel_stats[label] = {'count': len(group), 'avgER': round(sum(p['engagementRate'] for p in group)/len(group), 2), 'avgViews': round(sum(p['views'] for p in group)/len(group), 0)}

    # Computed insights
    best_type = max(type_stats.items(), key=lambda x: x[1]['avgER'])
    worst_type = min(type_stats.items(), key=lambda x: x[1]['avgER'])
    pillar_ranked = sorted(pillar_stats.items(), key=lambda x: x[1]['avgER'], reverse=True)
    best_day = max(day_stats.items(), key=lambda x: x[1]['avgER'])
    best_hour = max(hour_stats.items(), key=lambda x: x[1]['avgER'])
    cap_ranked = sorted(caption_stats.items(), key=lambda x: x[1]['avgER'], reverse=True)
    best_carousel = max(carousel_stats.items(), key=lambda x: x[1]['avgER']) if carousel_stats else ('N/A', {'avgER': 0})
    best_reel = max(reel_stats.items(), key=lambda x: x[1]['avgER']) if reel_stats else ('N/A', {'avgER': 0})

    q_posts = [p for p in data if p['hasQuestion']]
    no_q = [p for p in data if not p['hasQuestion']]
    q_er = round(sum(p['engagementRate'] for p in q_posts)/max(1,len(q_posts)), 2)
    no_q_er = round(sum(p['engagementRate'] for p in no_q)/max(1,len(no_q)), 2)

    video_posts = [p for p in data if p['type'] == 'Video']
    top_reel = max(video_posts, key=lambda x: x['views']) if video_posts else None

    type_name = lambda t: 'Reels' if t=='Video' else ('Carousels' if t=='Sidecar' else 'Images')

    insights = {
        'bestType': {'name': type_name(best_type[0]), 'er': best_type[1]['avgER'], 'count': best_type[1]['count']},
        'worstType': {'name': type_name(worst_type[0]), 'er': worst_type[1]['avgER']},
        'bestPillar': {'name': pillar_ranked[0][0], 'er': pillar_ranked[0][1]['avgER'], 'count': pillar_ranked[0][1]['count']},
        'worstPillar': {'name': pillar_ranked[-1][0], 'er': pillar_ranked[-1][1]['avgER']},
        'bestDay': {'name': best_day[0], 'er': best_day[1]['avgER']},
        'bestHourUTC': {'hour': int(best_hour[0]), 'er': best_hour[1]['avgER']},
        'captionInsight': f"{cap_ranked[0][0]} captions avg {cap_ranked[0][1]['avgER']}% vs {cap_ranked[-1][0]} at {cap_ranked[-1][1]['avgER']}%",
        'bestCarousel': {'slides': best_carousel[0], 'er': best_carousel[1]['avgER']},
        'bestReelDuration': {'range': best_reel[0], 'er': best_reel[1]['avgER']},
        'questionEffect': {'withQ': q_er, 'withoutQ': no_q_er, 'qCount': len(q_posts)},
        'topReelViews': top_reel['views'] if top_reel else 0,
        'topReelAvgViews': type_stats.get('Video', {}).get('avgViews', 0),
        'pillarMix': {p[0]: round(p[1]['count']/len(data)*100, 1) for p in pillar_ranked},
    }

    # Top/bottom posts
    top_posts = sorted(data, key=lambda x: x['engagementRate'], reverse=True)[:20]
    bottom_posts = sorted([p for p in data if p['likes'] > 0], key=lambda x: x['engagementRate'])[:10]

    dashboard = {
        'profile': profile, 'totalPosts': len(data),
        'dateRange': f"{data[-1]['date']} to {data[0]['date']}",
        'overallAvgER': round(sum(p['engagementRate'] for p in data)/len(data), 2),
        'overallAvgLikes': round(sum(p['likes'] for p in data)/len(data), 1),
        'overallAvgComments': round(sum(p['comments'] for p in data)/len(data), 1),
        'typeStats': type_stats, 'pillarStats': pillar_stats, 'dayStats': day_stats,
        'hourStats': hour_stats, 'monthlyPosting': monthly, 'captionStats': caption_stats,
        'carouselStats': carousel_stats, 'reelDurationStats': reel_stats, 'insights': insights,
        'topPosts': [{'url':p['url'],'hook':p['hook'][:100],'type':p['type'],'likes':p['likes'],'comments':p['comments'],'views':p['views'],'er':p['engagementRate'],'pillar':p['pillar'],'date':p['date']} for p in top_posts],
        'bottomPosts': [{'url':p['url'],'hook':p['hook'][:100],'type':p['type'],'likes':p['likes'],'comments':p['comments'],'er':p['engagementRate'],'pillar':p['pillar'],'date':p['date']} for p in bottom_posts],
        'topHooks': [{'hook':p['hook'][:120],'er':p['engagementRate'],'type':p['type'],'likes':p['likes']} for p in sorted(data, key=lambda x: x['engagementRate'], reverse=True)[:20]],
        'allPosts': [{'url':p['url'],'hook':p['hook'][:80],'caption':p['caption'][:200],'type':p['type'],'likes':p['likes'],'comments':p['comments'],'views':p['views'],'er':p['engagementRate'],'pillar':p['pillar'],'date':p['date'],'qualityScore':p['qualityScore']} for p in data],
        'lastUpdated': datetime.now().strftime('%Y-%m-%d'),
    }

    save_json("dashboard_data.json", dashboard)
    print(f"Analytics built -> dashboard_data.json")
    return dashboard


if __name__ == "__main__":
    data, profile = process_posts()
    build_analytics(data, profile)
    print("\nPipeline complete. Now run build_dashboard.py to generate HTML.")
