#!/usr/bin/env python3
"""Factory Dashboard V2 - Flask API Server"""

import subprocess
import json
import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import db as taskdb

app = Flask(__name__, static_folder='static')
CORS(app)

OPENCLAW_BASE = os.path.expanduser("~/.openclaw/agents")
OPENCLAW_CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")

# API pricing per million tokens (synced from LiteLLM 2026-02-16)
# Source: https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json
PRICING = {
    # Anthropic
    'claude-opus-4-6': {'input': 5.0, 'output': 25.0, 'cacheRead': 0.5, 'cacheWrite': 6.25},
    'claude-opus-4-5': {'input': 5.0, 'output': 25.0, 'cacheRead': 0.5, 'cacheWrite': 6.25},
    'claude-opus-4': {'input': 15.0, 'output': 75.0, 'cacheRead': 1.5, 'cacheWrite': 18.75},
    'claude-opus-4-1': {'input': 15.0, 'output': 75.0, 'cacheRead': 1.5, 'cacheWrite': 18.75},
    'claude-sonnet-4': {'input': 3.0, 'output': 15.0, 'cacheRead': 0.3, 'cacheWrite': 3.75},
    'claude-sonnet-4-20250514': {'input': 3.0, 'output': 15.0, 'cacheRead': 0.3, 'cacheWrite': 3.75},
    'claude-haiku-3-5': {'input': 0.8, 'output': 4.0, 'cacheRead': 0.08, 'cacheWrite': 1.0},
    # xAI
    'grok-4-1-fast': {'input': 0.20, 'output': 0.50, 'cacheRead': 0.05},
    'grok-4': {'input': 3.0, 'output': 15.0},
    'grok-2': {'input': 2.0, 'output': 10.0},
    # OpenAI
    'gpt-5.3-codex': {'input': 2.0, 'output': 8.0, 'cacheRead': 0.5},  # estimated from 5.0/5.2 trend
    'gpt-4.1': {'input': 2.0, 'output': 8.0, 'cacheRead': 0.5},
    'gpt-4o': {'input': 2.5, 'output': 10.0, 'cacheRead': 1.25},
    # Google Gemini
    'gemini-3-pro-preview': {'input': 1.25, 'output': 10.0, 'cacheRead': 0.125},
    'gemini-2.5-pro': {'input': 1.25, 'output': 10.0, 'cacheRead': 0.125},
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50, 'cacheRead': 0.03},
    'gemini-2.5-flash-preview-05-20': {'input': 0.30, 'output': 2.50, 'cacheRead': 0.03},
    'gemini-3-flash-preview': {'input': 0.50, 'output': 3.0, 'cacheRead': 0.05},
    # Default fallback
    'default': {'input': 3.0, 'output': 15.0},
}

SUBSCRIPTION_PRICING = {
    'anthropic_max': 200.0,       # Anthropic MAX
    'openai_plus': 20.0,          # ChatGPT Plus (개인)
    'google_ai_pro': 19.99,       # Google AI Pro (개인)
}
SUBSCRIPTION_TOTAL = sum(SUBSCRIPTION_PRICING.values())  # $650


def load_openclaw_config():
    """Returns {agent_id: {'model': 'model-name', 'provider': 'provider'}}"""
    try:
        with open(OPENCLAW_CONFIG, 'r') as f:
            config = json.load(f)
        mapping = {}
        # Get defaults
        defaults = config.get('agents', {}).get('defaults', {})
        default_model_cfg = defaults.get('model', {})
        default_full_model = default_model_cfg.get('primary', '') if isinstance(default_model_cfg, dict) else default_model_cfg
        default_provider, default_model = ('unknown', default_full_model)
        if default_full_model and '/' in default_full_model:
            default_provider, default_model = default_full_model.split('/', 1)

        for agent in config.get('agents', {}).get('list', []):
            aid = agent.get('id')
            full_model = agent.get('model', '')
            if isinstance(full_model, dict):
                full_model = full_model.get('primary', '')
            if aid:
                if full_model and '/' in full_model:
                    provider, model = full_model.split('/', 1)
                elif full_model:
                    provider, model = 'unknown', full_model
                else:
                    # Inherit from defaults
                    provider, model = default_provider, default_model
                mapping[aid] = {'model': model, 'provider': provider}
        return mapping
    except Exception:
        return {}


def get_pricing(model_name):
    if not model_name:
        return PRICING['default']
    ml = model_name.lower()
    if ml in PRICING:
        return PRICING[ml]
    for key in PRICING:
        if key in ml:
            return PRICING[key]
    if 'opus' in ml:
        return PRICING['claude-opus-4-6']
    elif 'sonnet' in ml:
        return PRICING['claude-sonnet-4']
    elif 'haiku' in ml:
        return PRICING['claude-haiku-3-5']
    elif 'grok' in ml:
        return PRICING.get('grok-4-1-fast', PRICING['default'])
    elif 'gemini' in ml:
        return PRICING.get('gemini-3-pro-preview', PRICING['default'])
    elif 'codex' in ml or 'gpt' in ml:
        return PRICING.get('gpt-5.3-codex', PRICING['default'])
    return PRICING['default']


def classify_model(model_name, agent_id, agent_configs):
    """Returns (subscription_key or None, plan_type)
    plan_type: 'subscription', 'payperuse', 'free'
    """
    if not model_name or model_name == 'delivery-mirror':
        return None, 'free'

    ml = model_name.lower()

    # Claude models → anthropic_max
    if 'claude' in ml:
        return 'anthropic_max', 'subscription'

    # GPT/Codex → openai_pro
    if 'gpt' in ml or 'codex' in ml:
        return 'openai_plus', 'subscription'

    # Grok → pay-per-use
    if 'grok' in ml:
        return None, 'payperuse'

    # Gemini: check auth profiles and agent config for provider
    if 'gemini' in ml:
        # First check agent config
        agent_cfg = agent_configs.get(agent_id, {})
        provider = agent_cfg.get('provider', '')
        if provider == 'google-gemini-cli':
            return 'google_ai_pro', 'subscription'
        elif provider == 'google':
            return None, 'payperuse'
        # Check if google-gemini-cli auth exists (OAuth = subscription)
        try:
            with open(OPENCLAW_CONFIG, 'r') as f:
                cfg = json.load(f)
            auth_profiles = cfg.get('auth', {}).get('profiles', {})
            for profile_key, profile in auth_profiles.items():
                if profile.get('provider') == 'google-gemini-cli':
                    return 'google_ai_pro', 'subscription'
        except Exception:
            pass
        # Fallback: check other agent configs
        for aid, cfg in agent_configs.items():
            if cfg.get('provider') == 'google-gemini-cli':
                return 'google_ai_pro', 'subscription'
        return None, 'payperuse'

    return None, 'free'


def resolve_agent_name(agent_dir, session_key=''):
    """Resolve agent name: main→MJ, detect cron/subagent from session key."""
    agent = agent_dir
    if agent == 'main':
        agent = 'MJ'
    return agent


def determine_billing_type(cost_total, model_name, agent_dir, agent_configs):
    """
    Determine billing type based on model classification AND actual cost.
    - Claude models: always 'subscription' (Anthropic MAX)
    - GPT/Codex models: always 'subscription' (OpenAI Pro)
    - Gemini models via google-gemini-cli: 'subscription' if cost==0, 'payperuse' if cost>0
    - Grok models: always 'payperuse'
    """
    sub_key, plan_type = classify_model(model_name, agent_dir, agent_configs)
    
    if plan_type == 'subscription':
        # For Gemini, check if this specific message was actually free (OAuth) or paid (API key)
        if sub_key == 'google_ai_pro' and cost_total and cost_total > 0:
            return 'payperuse'
        return 'subscription'
    elif plan_type == 'payperuse':
        return 'payperuse'
    else:
        return 'free'


def parse_transcripts(date_from=None, date_to=None):
    agent_configs = load_openclaw_config()

    agents = {}
    daily_agent_cost = defaultdict(lambda: defaultdict(float))
    daily_model_cost = defaultdict(lambda: defaultdict(float))
    daily_agent_tokens = defaultdict(lambda: defaultdict(int))
    daily_model_tokens = defaultdict(lambda: defaultdict(int))
    agent_model_matrix = defaultdict(lambda: defaultdict(float))
    # model_billing_key = "model_name|billing_type" for split display
    model_billing_tokens = defaultdict(lambda: {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0})
    model_billing_cost = defaultdict(float)
    model_billing_agents = defaultdict(set)
    subscription_usage = defaultdict(float)
    total_cost = 0.0
    earliest = None
    latest = None
    active_dates = set()

    try:
        for agent_dir in os.listdir(OPENCLAW_BASE):
            sessions_dir = os.path.join(OPENCLAW_BASE, agent_dir, 'sessions')
            if not os.path.isdir(sessions_dir):
                continue

            resolved_agent = resolve_agent_name(agent_dir)
            agent_cfg = agent_configs.get(agent_dir, {})
            if not agent_cfg and agent_dir == 'main':
                agent_cfg = agent_configs.get('MJ', {})
            agent_model = agent_cfg.get('model', 'unknown')

            for fname in os.listdir(sessions_dir):
                if not fname.endswith('.jsonl'):
                    continue
                fpath = os.path.join(sessions_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                entry = json.loads(line.strip())
                            except json.JSONDecodeError:
                                continue

                            if entry.get('type') != 'message':
                                continue
                            msg = entry.get('message', {})
                            if msg.get('role') != 'assistant':
                                continue
                            usage = msg.get('usage', {})
                            if not usage or 'cost' not in usage:
                                continue

                            ts = entry.get('timestamp')
                            if not ts:
                                continue
                            try:
                                if isinstance(ts, str):
                                    msg_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                else:
                                    msg_dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                            except Exception:
                                continue

                            date_str = msg_dt.strftime('%Y-%m-%d')
                            if date_from and date_str < date_from:
                                continue
                            if date_to and date_str > date_to:
                                continue

                            cost_data = usage.get('cost', {})
                            oc_cost = cost_data.get('total', 0.0) if isinstance(cost_data, dict) else 0.0

                            inp = usage.get('input', 0)
                            out = usage.get('output', 0)
                            cr = usage.get('cacheRead', 0)
                            cw = usage.get('cacheWrite', 0)

                            message_model = msg.get('model', agent_model)

                            # Calculate cost from our pricing table (not OpenClaw's)
                            p = get_pricing(message_model)
                            mc = ((inp / 1e6) * p.get('input', 0) +
                                  (out / 1e6) * p.get('output', 0) +
                                  (cr / 1e6) * p.get('cacheRead', p.get('input', 0) * 0.1) +
                                  (cw / 1e6) * p.get('cacheWrite', p.get('input', 0) * 1.25))

                            # Determine billing type (use OpenClaw's cost to detect API key vs OAuth for Gemini)
                            billing_type = determine_billing_type(oc_cost, message_model, agent_dir, agent_configs)

                            # Classify for subscription tracking
                            sub_key, plan_type = classify_model(message_model, agent_dir, agent_configs)
                            if sub_key and billing_type == 'subscription':
                                subscription_usage[sub_key] += mc

                            # Track by resolved agent (main→arc)
                            if resolved_agent not in agents:
                                agents[resolved_agent] = {
                                    'cost': 0.0, 'input': 0, 'output': 0,
                                    'cacheRead': 0, 'cacheWrite': 0, 'tokens': 0,
                                    'model': agent_model,
                                }
                            ad = agents[resolved_agent]
                            ad['cost'] += mc
                            ad['input'] += inp
                            ad['output'] += out
                            ad['cacheRead'] += cr
                            ad['cacheWrite'] += cw
                            ad['tokens'] += inp + out + cr
                            total_cost += mc

                            daily_agent_cost[date_str][resolved_agent] += mc
                            daily_model_cost[date_str][message_model] += mc
                            daily_agent_tokens[date_str][resolved_agent] += inp + out + cr
                            daily_model_tokens[date_str][message_model] += inp + out + cr
                            agent_model_matrix[resolved_agent][message_model] += mc
                            active_dates.add(date_str)

                            # Model+billing split tracking
                            mb_key = f"{message_model}|{billing_type}"
                            mt = model_billing_tokens[mb_key]
                            mt['input'] += inp
                            mt['output'] += out
                            mt['cacheRead'] += cr
                            mt['cacheWrite'] += cw
                            model_billing_cost[mb_key] += mc
                            model_billing_agents[mb_key].add(resolved_agent)

                            if earliest is None or msg_dt < earliest:
                                earliest = msg_dt
                            if latest is None or msg_dt > latest:
                                latest = msg_dt

                except Exception:
                    continue

    except Exception:
        return None

    # Remove agents with zero activity
    agents = {k: v for k, v in agents.items() if v['cost'] > 0 or v['tokens'] > 0}

    days = max(1, (latest - earliest).days + 1) if earliest and latest else 1
    daily_cost = total_cost / days
    monthly_cost = daily_cost * 30

    # Build byModel with billing split
    by_model = {}
    for mb_key, cost in model_billing_cost.items():
        model_name, billing_type = mb_key.split('|', 1)

        # Display name: add suffix if model has both types
        other_key = f"{model_name}|{'subscription' if billing_type == 'payperuse' else 'payperuse'}"
        has_both = other_key in model_billing_cost

        if has_both:
            display_name = f"{model_name} ({'종량제' if billing_type == 'payperuse' else '구독'})"
        else:
            display_name = model_name

        mt = model_billing_tokens[mb_key]
        plan_label = billing_type if billing_type == 'payperuse' else 'subscription'

        by_model[display_name] = {
            'agents': sorted(model_billing_agents[mb_key]),
            'totalCost': round(cost, 4),
            'pricing': get_pricing(model_name),
            'input': mt['input'],
            'output': mt['output'],
            'cacheRead': mt['cacheRead'],
            'cacheWrite': mt['cacheWrite'],
            'planType': plan_label,
            'monthlyCost': round(cost / days * 30, 2) if days > 0 else 0,
        }

    # Subscription breakdown
    sub_breakdown = {}
    for key, price in SUBSCRIPTION_PRICING.items():
        est = round(subscription_usage.get(key, 0), 2)
        sub_breakdown[key] = {
            'price': price,
            'estimatedApiCost': est,
            'savings': round(est - price, 2),
            'utilization': round((est / price) * 100, 1) if price > 0 else 0,
        }

    total_est = sum(v['estimatedApiCost'] for v in sub_breakdown.values())
    utilization = round((total_est / SUBSCRIPTION_TOTAL) * 100, 1) if SUBSCRIPTION_TOTAL > 0 else 0

    total_input = sum(a['input'] for a in agents.values())
    total_output = sum(a['output'] for a in agents.values())
    total_cache_read = sum(a['cacheRead'] for a in agents.values())
    total_cache_write = sum(a['cacheWrite'] for a in agents.values())

    payperuse_cost = 0.0
    for mn, bm in by_model.items():
        if bm.get('planType') == 'payperuse':
            payperuse_cost += bm['totalCost']

    # Sort agent keys: arc first, then alphabetical
    agent_order = ['MJ', 'bori', 'mir', 'nova', 'lerobot', 'voice']
    def agent_sort_key(name):
        try:
            return (0, agent_order.index(name))
        except ValueError:
            return (1, name)

    sorted_agents = dict(sorted(agents.items(), key=lambda x: agent_sort_key(x[0])))

    return {
        'totalCost': round(total_cost, 2),
        'dailyCost': round(daily_cost, 2),
        'monthlyCost': round(monthly_cost, 2),
        'daysRunning': days,
        'activeDays': len(active_dates),
        'subscriptionTotal': round(SUBSCRIPTION_TOTAL, 2),
        'subscriptionBreakdown': sub_breakdown,
        'utilization': utilization,
        'totalEstimatedApiCost': round(total_est, 2),
        'payperUseCost': round(payperuse_cost, 2),
        'totalTokens': total_input + total_output + total_cache_read,
        'totalInput': total_input,
        'totalOutput': total_output,
        'totalCacheRead': total_cache_read,
        'totalCacheWrite': total_cache_write,
        'byAgent': {a: {
            'cost': round(d['cost'], 2),
            'tokens': d['tokens'],
            'input': d['input'],
            'output': d['output'],
            'cacheRead': d['cacheRead'],
            'cacheWrite': d['cacheWrite'],
            'model': d['model'],
        } for a, d in sorted_agents.items()},
        'byModel': by_model,
        'dailyCostByAgent': [
            {'date': ds, **{a: round(v, 4) for a, v in daily_agent_cost[ds].items()}}
            for ds in sorted(daily_agent_cost.keys())
        ],
        'dailyCostByModel': [
            {'date': ds, **{m: round(v, 4) for m, v in daily_model_cost[ds].items()}}
            for ds in sorted(daily_model_cost.keys())
        ],
        'dailyTokensByAgent': [
            {'date': ds, **{a: v for a, v in daily_agent_tokens[ds].items()}}
            for ds in sorted(daily_agent_tokens.keys())
        ],
        'dailyTokensByModel': [
            {'date': ds, **{m: v for m, v in daily_model_tokens[ds].items()}}
            for ds in sorted(daily_model_tokens.keys())
        ],
        'agentModelMatrix': {
            a: {m: round(c, 4) for m, c in models.items()}
            for a, models in agent_model_matrix.items()
        },
        'dateRange': {
            'start': earliest.isoformat() if earliest else None,
            'end': latest.isoformat() if latest else None,
        }
    }


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/sessions')
def get_sessions():
    try:
        date_from = request.args.get('from')
        date_to = request.args.get('to')

        result = subprocess.run(
            ['openclaw', 'sessions', '--json', '--active', '120'],
            capture_output=True, text=True, check=True, timeout=10
        )
        data = json.loads(result.stdout)

        sessions = {'subagents': [], 'cron': [], 'main': None}

        for session in data.get('sessions', []):
            key = session.get('key', '')
            age_ms = session.get('ageMs', 99999)
            tokens_in = session.get('inputTokens', 0) or session.get('totalInputTokens', 0) or 0
            tokens_out = session.get('outputTokens', 0) or session.get('totalOutputTokens', 0) or 0
            model = session.get('model', 'unknown')

            pricing = get_pricing(model)
            cost = (tokens_in / 1e6) * pricing['input'] + (tokens_out / 1e6) * pricing['output']

            status = 'active' if age_ms < 60000 else 'idle'
            sd = {
                'id': key.split(':')[-1] if ':' in key else key,
                'key': key, 'model': model,
                'updatedAt': session.get('updatedAt'),
                'ageMs': age_ms, 'status': status,
                'tokensIn': tokens_in, 'tokensOut': tokens_out,
                'tokens': tokens_in + tokens_out,
                'cost': round(cost, 2),
                'contextTokens': session.get('contextTokens', 0),
            }

            if ':subagent:' in key:
                sessions['subagents'].append(sd)
            elif ':cron:' in key:
                sessions['cron'].append(sd)
            elif key == 'agent:main:main':
                sessions['main'] = sd

        stats = {
            'total': len(data.get('sessions', [])),
            'subagents': len(sessions['subagents']),
            'cron': len(sessions['cron']),
            'activeSubagents': len([s for s in sessions['subagents'] if s['status'] == 'active']),
        }

        cumulative = parse_transcripts(date_from, date_to)

        return jsonify({
            'success': True,
            'sessions': sessions,
            'stats': stats,
            'cumulative': cumulative,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'factory-dashboard-v2'})


# ── Task Queue API ────────────────────────────────────

@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json(force=True) if request.is_json else {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'title is required'}), 400
    description = data.get('description', '')
    status = data.get('status', 'pending')
    priority = data.get('priority', 5)
    try:
        priority = int(priority)
    except (ValueError, TypeError):
        priority = 5
    task = taskdb.create_task(title=title, description=description, status=status, priority=priority)
    return jsonify({'success': True, 'task': task}), 201


@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    status = request.args.get('status')
    priority = request.args.get('priority')
    tasks = taskdb.list_tasks(status=status, priority=priority)
    return jsonify({'success': True, 'tasks': tasks, 'total': len(tasks)})


@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = taskdb.get_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': 'not found'}), 404
    return jsonify({'success': True, 'task': task})


@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    existing = taskdb.get_task(task_id)
    if not existing:
        return jsonify({'success': False, 'error': 'not found'}), 404
    data = request.get_json(force=True) if request.is_json else {}
    task = taskdb.update_task(
        task_id,
        title=data.get('title'),
        description=data.get('description'),
        status=data.get('status'),
        priority=data.get('priority'),
    )
    return jsonify({'success': True, 'task': task})


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    deleted = taskdb.delete_task(task_id)
    if not deleted:
        return jsonify({'success': False, 'error': 'not found'}), 404
    return jsonify({'success': True})


if __name__ == '__main__':
    taskdb.init_db()
    print("Factory Dashboard V2 - http://localhost:5051")
    app.run(debug=False, port=5051, host='0.0.0.0')
