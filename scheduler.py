"""
TaskScheduler — Auto-spawn agent for pending tasks.

Phase 2 of Factory Dashboard V2.
Monitors the task queue and spawns OpenClaw agents for pending tasks
with safety guardrails (concurrency, budget, model whitelist).
"""

import threading
import subprocess
import json
import logging
import time
import os
from datetime import datetime, timezone

import db as taskdb

logger = logging.getLogger('scheduler')


class TaskScheduler:
    """
    Daemon scheduler that polls the task queue and auto-spawns OpenClaw agents.

    Safety guardrails:
    - MAX_CONCURRENT: max simultaneous running agents (default: 3)
    - DAILY_BUDGET: daily cost limit in USD (default: $20)
    - MODEL_WHITELIST: only these model families allowed for auto-spawn
    - POLL_INTERVAL: seconds between queue checks (default: 30)
    """

    DEFAULT_CONFIG = {
        'max_concurrent': 3,
        'daily_budget': 20.0,
        'poll_interval': 30,
        'model_whitelist': ['opus', 'sonnet'],
        'default_model': 'anthropic/claude-sonnet-4',
        'dry_run': False,
        'timeout_seconds': 600,
    }

    def __init__(self):
        self._config = dict(self.DEFAULT_CONFIG)
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._active_agents = {}  # task_id -> process info
        self._spawn_log = []      # recent spawn events
        self._stats = {
            'total_spawned': 0,
            'total_completed': 0,
            'total_failed': 0,
            'started_at': None,
        }

    # ── Configuration ─────────────────────────────────

    @property
    def config(self):
        return dict(self._config)

    def update_config(self, **kwargs):
        allowed = set(self.DEFAULT_CONFIG.keys())
        for k, v in kwargs.items():
            if k in allowed:
                self._config[k] = v
        logger.info(f"Scheduler config updated: {kwargs}")

    @property
    def is_running(self):
        return self._running

    # ── Start / Stop ──────────────────────────────────

    def start(self):
        with self._lock:
            if self._running:
                return {'status': 'already_running'}
            self._running = True
            self._stats['started_at'] = datetime.now(timezone.utc).isoformat()
            self._thread = threading.Thread(target=self._loop, daemon=True, name='TaskScheduler')
            self._thread.start()
            logger.info("TaskScheduler started")
            return {'status': 'started'}

    def stop(self):
        with self._lock:
            if not self._running:
                return {'status': 'already_stopped'}
            self._running = False
            logger.info("TaskScheduler stopping...")
            return {'status': 'stopped'}

    # ── Main Loop ─────────────────────────────────────

    def _loop(self):
        logger.info("Scheduler loop started")
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}", exc_info=True)
            time.sleep(self._config['poll_interval'])
        logger.info("Scheduler loop ended")

    def _tick(self):
        """One scheduler cycle: check active agents, spawn new ones if slots available."""
        # 1. Update status of active agents
        self._check_active_agents()

        # 2. Count running tasks
        running_count = taskdb.count_tasks_by_status('running')
        max_concurrent = self._config['max_concurrent']

        if running_count >= max_concurrent:
            logger.debug(f"At capacity: {running_count}/{max_concurrent} agents running")
            return

        # 3. Check daily budget
        today_cost = taskdb.get_today_spawned_cost()
        daily_budget = self._config['daily_budget']
        if today_cost >= daily_budget:
            logger.warning(f"Daily budget exhausted: ${today_cost:.2f} >= ${daily_budget:.2f}")
            return

        # 4. Get pending tasks (priority order)
        slots = max_concurrent - running_count
        pending = taskdb.get_pending_tasks(limit=slots)

        if not pending:
            logger.debug("No pending tasks")
            return

        # 5. Spawn agents for each pending task
        for task in pending:
            if not self._running:
                break
            try:
                self._spawn_agent(task)
            except Exception as e:
                logger.error(f"Failed to spawn for task {task['id']}: {e}")
                taskdb.transition_task(
                    task['id'], 'failed',
                    error_message=f"Spawn failed: {str(e)}"
                )
                self._stats['total_failed'] += 1

    # ── Agent Spawning ────────────────────────────────

    def _spawn_agent(self, task):
        """Spawn an OpenClaw agent for a task."""
        task_id = task['id']
        title = task['title']
        description = task.get('description', '')
        model = task.get('model') or self._config['default_model']

        # Validate model against whitelist
        if not self._is_model_allowed(model):
            logger.warning(f"Model '{model}' not in whitelist, using default")
            model = self._config['default_model']

        # Build the prompt
        prompt = f"Task: {title}"
        if description:
            prompt += f"\n\nDetails:\n{description}"

        # Transition to queued first
        taskdb.transition_task(task_id, 'queued', model=model)

        dry_run = self._config['dry_run']

        if dry_run:
            # Dry-run: simulate spawn
            logger.info(f"[DRY-RUN] Would spawn agent for task {task_id}: {title}")
            session_key = f"dry-run-{task_id}"
            taskdb.transition_task(
                task_id, 'running',
                session_key=session_key,
                agent_id='dry-run',
                model=model,
            )
            self._active_agents[task_id] = {
                'session_key': session_key,
                'process': None,
                'dry_run': True,
                'spawned_at': datetime.now(timezone.utc).isoformat(),
            }
            # Auto-complete dry-run tasks after a short delay
            self._auto_complete_dry_run(task_id)
        else:
            # Real spawn: call openclaw agent CLI
            cmd = [
                'openclaw', 'agent',
                '--message', prompt,
                '--json',
                '--timeout', str(self._config['timeout_seconds']),
            ]

            logger.info(f"Spawning agent for task {task_id}: {title} (model: {model})")

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                session_key = f"task-{task_id}"
                taskdb.transition_task(
                    task_id, 'running',
                    session_key=session_key,
                    agent_id='main',
                    model=model,
                )

                self._active_agents[task_id] = {
                    'session_key': session_key,
                    'process': proc,
                    'dry_run': False,
                    'spawned_at': datetime.now(timezone.utc).isoformat(),
                }
            except FileNotFoundError:
                raise RuntimeError("openclaw CLI not found in PATH")

        self._stats['total_spawned'] += 1
        self._spawn_log.append({
            'task_id': task_id,
            'title': title,
            'model': model,
            'dry_run': dry_run,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        # Keep log trimmed
        if len(self._spawn_log) > 50:
            self._spawn_log = self._spawn_log[-50:]

    def _auto_complete_dry_run(self, task_id):
        """Auto-complete a dry-run task after a short delay (simulates completion)."""
        def _complete():
            time.sleep(5)  # Simulate 5 second execution
            if task_id in self._active_agents:
                taskdb.transition_task(
                    task_id, 'done',
                    result_summary='[DRY-RUN] Task completed successfully (simulated)',
                )
                del self._active_agents[task_id]
                self._stats['total_completed'] += 1
                logger.info(f"[DRY-RUN] Task {task_id} auto-completed")

        t = threading.Thread(target=_complete, daemon=True)
        t.start()

    def _is_model_allowed(self, model):
        """Check if model is in the whitelist."""
        if not model:
            return True
        model_lower = model.lower()
        return any(allowed in model_lower for allowed in self._config['model_whitelist'])

    # ── Active Agent Monitoring ───────────────────────

    def _check_active_agents(self):
        """Check status of active agent processes and update task status."""
        completed = []
        for task_id, info in list(self._active_agents.items()):
            if info.get('dry_run'):
                continue  # Handled by auto_complete_dry_run

            proc = info.get('process')
            if proc is None:
                continue

            retcode = proc.poll()
            if retcode is not None:
                # Process finished
                stdout = ''
                stderr = ''
                try:
                    stdout = proc.stdout.read() if proc.stdout else ''
                    stderr = proc.stderr.read() if proc.stderr else ''
                except Exception:
                    pass

                if retcode == 0:
                    # Parse result
                    result_summary = self._parse_agent_result(stdout)
                    taskdb.transition_task(
                        task_id, 'done',
                        result_summary=result_summary or 'Completed successfully',
                    )
                    self._stats['total_completed'] += 1
                    logger.info(f"Task {task_id} completed (exit 0)")
                else:
                    error_msg = stderr[:500] if stderr else f"Exit code {retcode}"
                    taskdb.transition_task(
                        task_id, 'failed',
                        error_message=error_msg,
                    )
                    self._stats['total_failed'] += 1
                    logger.warning(f"Task {task_id} failed: {error_msg[:100]}")

                completed.append(task_id)

        for task_id in completed:
            del self._active_agents[task_id]

    def _parse_agent_result(self, stdout):
        """Try to parse JSON output from openclaw agent."""
        if not stdout:
            return None
        try:
            data = json.loads(stdout)
            # Extract useful summary from agent response
            if isinstance(data, dict):
                return data.get('reply', data.get('message', str(data)))[:500]
        except json.JSONDecodeError:
            return stdout[:500] if stdout else None
        return None

    # ── Status ────────────────────────────────────────

    def get_status(self):
        """Get current scheduler status."""
        running_count = taskdb.count_tasks_by_status('running')
        pending_count = taskdb.count_tasks_by_status('pending')
        queued_count = taskdb.count_tasks_by_status('queued')
        today_cost = taskdb.get_today_spawned_cost()

        return {
            'is_running': self._running,
            'config': self.config,
            'active_agents': len(self._active_agents),
            'active_agent_ids': list(self._active_agents.keys()),
            'running_tasks': running_count,
            'pending_tasks': pending_count,
            'queued_tasks': queued_count,
            'today_cost': round(today_cost, 2),
            'daily_budget': self._config['daily_budget'],
            'budget_remaining': round(self._config['daily_budget'] - today_cost, 2),
            'stats': dict(self._stats),
            'recent_spawns': self._spawn_log[-10:],
        }
