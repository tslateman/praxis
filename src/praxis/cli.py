"""praxis CLI -- pragmatic leverage for getting shit done.

Operational synthesis layer over Lore. Reads from Lore's memory,
synthesizes actionable views.
"""

import argparse
import json
import subprocess
import sys

from praxis import synthesis, watchdog


def parse_time(val: str) -> int:
    """Parse time string like 10m, 5s to seconds."""
    if val.endswith("m"):
        return int(val[:-1]) * 60
    if val.endswith("h"):
        return int(val[:-1]) * 3600
    if val.endswith("s"):
        return int(val[:-1])
    return int(val)


def cmd_watchdog(args):
    """Run watchdog to monitor command failures."""
    window_sec = parse_time(args.window)
    interval_sec = parse_time(args.interval)

    watchdog.run_watchdog(
        cmd=args.cmd,
        project=args.project,
        window_sec=window_sec,
        threshold=args.threshold,
        interval_sec=interval_sec,
    )


def cmd_watchdog_report(args):
    """Summary of recent watchdog failures."""
    watchdog.report_status()


def cmd_status(args):
    """Where am I? Active goals, blockers, pulse."""
    result = synthesis.status()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    pulse = result["pulse"].upper()
    print(f"Pulse: {pulse}")
    print()

    tasks = result.get("tasks", {})
    if tasks:
        print("SpecTrace Tasks:")
        for status, count in sorted(tasks.items()):
            print(f"  {status}: {count}")
        print()

    goals = result["active_goals"]
    if goals:
        print(f"Active Goals ({len(goals)}):")
        for g in goals:
            print(f"  {g.get('id', '?')}: {g.get('name', 'unnamed')}")
    else:
        print("No active goals.")

    verification = result.get("verification")
    if verification and verification != "unavailable":
        print()
        print(f"Verification: {verification.upper()}")

    blockers = result["blockers"]
    if blockers["recent_failures"] > 0 or blockers["stale_signals"] > 0:
        print()
        print("Blockers:")
        if blockers["recent_failures"] > 0:
            print(f"  {blockers['recent_failures']} failures (last 7 days)")
        if blockers["stale_signals"] > 0:
            print(f"  {blockers['stale_signals']} stale signals")


def cmd_next(args):
    """What should I work on? Prioritized work queue."""
    result = synthesis.next_work()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if not result:
        print("Nothing in the queue. Create goals with `lore goal create`.")
        return

    print("Work Queue:")
    for i, m in enumerate(result[:10], 1):  # Top 10
        status_str = m.get("status", "?")
        marker = ">" if status_str == "in_progress" else " "
        type_str = m.get("type", "goal").upper()
        print(f"{marker} {i}. [{type_str}][{status_str}] {m.get('name', 'unnamed')}")

    if len(result) > 10:
        print(f"... and {len(result) - 10} more")


def cmd_blockers(args):
    """What's in the way? Failures, stale, friction."""
    result = synthesis.blockers_view()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    failures = result["failures"]
    if failures["count"] > 0:
        print(f"Failures ({failures['count']} recent):")
        for et, count in failures["by_type"].items():
            print(f"  {et}: {count}")
    else:
        print("No recent failures.")

    stale_data = result["stale"]
    if stale_data["count"] > 0:
        print()
        print(f"Stale Signals ({stale_data['count']}):")
        for o in stale_data["signals"][:5]:
            print(f"  {o.get('id', '?')}: {o.get('content', '')[:50]}")

    friction_data = result["friction"]
    if friction_data:
        print()
        print("Friction Points:")
        for f in friction_data:
            print(f"  {f['boundary']}: {f['failure_count']} failures")

    verification = result.get("verification")
    if verification:
        print()
        print(f"Verification ({verification['status'].upper()}):")
        for item in verification["items"]:
            if item["type"] == "high_risk_failing":
                print(f"  FAILING: {item['id']} {item['title']}")
            elif item["type"] == "stale_link":
                print(f"  STALE: {item['test_nodeid']} -> {item['requirement']}")


def cmd_health(args):
    """Ecosystem health summary."""
    result = synthesis.health()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    status_val = result["status"].upper()
    summary = result["summary"]

    print(f"Ecosystem Health: {status_val}")
    print()
    print("Summary:")
    print(
        f"  Failures: {summary['total_failures']} total, "
        f"{summary['recent_failures']} recent (7 days)"
    )
    print(f"  Triggers: {summary['trigger_count']} error types hitting threshold")
    print(f"  Stale: {summary['stale_count']} signals aging without action")
    print(f"  Blind spots: {summary['blind_spot_count']}")
    print(f"  Friction: {summary['friction_boundaries']} project boundaries")
    print(f"  Overlap: {summary['overlap_count']} command name conflicts")
    print(f"  Complexity: {summary['complexity_warnings']} projects exceed thresholds")
    print(
        f"  Undocumented: {summary['undocumented_decisions']} decisions, "
        f"{summary['undocumented_patterns']} patterns"
    )
    print(f"  Refinement: {summary['refinement_count']} opportunities")

    if result["triggers"]:
        print()
        print("Triggers:")
        for t in result["triggers"]:
            print(f"  {t['error_type']}: {t['count']} failures")

    if result["stale_signals"]:
        print()
        print("Stale Signals:")
        for o in result["stale_signals"][:5]:
            print(
                f"  {o.get('id', '?')}  {o.get('timestamp', '')[:10]}  "
                f'"{o.get("content", "")[:40]}"'
            )

    if result["blind_spots"]:
        print()
        print("Blind Spots:")
        for b in result["blind_spots"]:
            print(f"  {b['error_type']}: {b['count']} failures")

    if result["friction"]:
        print()
        print("Friction:")
        for f in result["friction"]:
            print(f"  {f['boundary']}: {f['failure_count']} failures")

    if result["overlap"]:
        print()
        print("Overlap:")
        for o in result["overlap"]:
            projs = ", ".join(o["projects"])
            print(f"  `{o['command']}` — {projs}")
        print()
        print("  Fix: Rename or consolidate commands in owning project")

    if result["complexity"]:
        print()
        print("Complexity:")
        for c in result["complexity"]:
            count = c["command_count"]
            thresh = c["threshold"]
            print(f"  {c['project']}: {count} commands (threshold: {thresh})")
        print()
        print(
            "  Fix: Group related commands under subcommands,"
            " remove rarely-used options"
        )

    undoc = result["undocumented"]
    if undoc["decisions"] or undoc["patterns"]:
        print()
        print("Undocumented:")
        for d in undoc["decisions"][:5]:
            print(f'  {d["id"]}: "{d["decision"]}" (no rationale)')
        for p in undoc["patterns"][:5]:
            missing = ", ".join(p["missing"])
            print(f'  {p["id"]}: "{p["name"]}" (missing: {missing})')
        print()
        if undoc["decisions"]:
            print('  Fix: lore remember "<decision>" --rationale "why"')
        if undoc["patterns"]:
            print('  Fix: lore learn "<pattern>" --problem "what it solves"')

    v = result.get("verification", {})
    if v.get("status") and v["status"] != "unavailable":
        print()
        v_status = v["status"].upper()
        cov = v.get("coverage") or {}
        print(f"Verification: {v_status}")
        if cov:
            print(
                f"  Coverage: {cov.get('passing', 0)} passing, "
                f"{cov.get('failing', 0)} failing, "
                f"{cov.get('untested', 0)} untested"
            )
        print(f"  Orphans: {v.get('orphan_count', 0)}")
        print(f"  Stale links: {v.get('stale_link_count', 0)}")


def cmd_verify(args):
    """Ground-truth verification: does code match the written record?"""
    result = synthesis.verify()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    status_val = result["status"].upper()
    print(f"Verification: {status_val}")

    if result["status"] == "unavailable":
        print("  SpecTrace DB not found.")
        return

    # Coverage
    cov = result.get("coverage") or {}
    if cov:
        print()
        print("Coverage:")
        print(
            f"  {cov['passing']} passing, {cov['failing']} failing, "
            f"{cov['untested']} untested ({cov['total']} total)"
        )

    # Last run
    last = result.get("last_run")
    if last:
        print()
        print("Last Test Run:")
        print(f"  {last.get('imported_at', '?')}")
        print(
            f"  {last.get('passed', 0)} passed, {last.get('failed', 0)} failed, "
            f"{last.get('errors', 0)} errors, {last.get('skipped', 0)} skipped"
        )
        if last.get("git_branch"):
            print(f"  Branch: {last['git_branch']}")
        if last.get("git_sha"):
            print(f"  SHA: {last['git_sha'][:12]}")

    # Orphans
    orphans = result.get("orphans", [])
    if orphans:
        print()
        print(f"Orphan Requirements ({result['orphan_count']}):")
        for o in orphans[:10]:
            risk = o.get("risk_level", "?")
            print(f"  {o['external_id']}  [{risk}]  {o['title']}")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more")

    # Stale links
    stale = result.get("stale_links", [])
    if stale:
        print()
        print(f"Stale Test Links ({result['stale_link_count']}):")
        for s in stale[:10]:
            print(f"  {s['test_nodeid']} -> {s['req_external_id']}")
        if len(stale) > 10:
            print(f"  ... and {len(stale) - 10} more")

    # High-risk issues
    hr = result.get("high_risk", {})
    if hr.get("failing"):
        print()
        print("High-Risk Failing:")
        for h in hr["failing"]:
            print(
                f"  {h['external_id']}  [{h['risk_level']}]  "
                f"{h['title']}  ({h['failing_count']} failing)"
            )
    if hr.get("untested"):
        print()
        print("High-Risk Untested:")
        for h in hr["untested"]:
            print(f"  {h['external_id']}  [{h['risk_level']}]  {h['title']}")

    # Integration risks
    integration = result.get("integration_risks", [])
    if integration:
        print()
        print("Integration Risks:")
        for r in integration:
            print(f"  [{r['level']}] {r['task_a']} <-> {r['task_b']} ({r['reason']})")


def cmd_triggers(args):
    """Error types hitting Rule of Three."""
    results = synthesis.triggers(threshold=args.threshold)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No error types have hit the threshold.")
        return

    for t in results:
        print(f"  {t['error_type']}: {t['count']} failures")


def cmd_stale(args):
    """Observations aging without action."""
    result = synthesis.stale(days=args.days)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    sigs = result["stale_signals"]
    if not sigs:
        print(f"No stale signals (threshold: {args.days} days).")
        return

    print(f"Stale signals (> {args.days} days):")
    for o in sigs:
        print(
            f"  {o.get('id', '?')}  {o.get('timestamp', '')[:10]}  "
            f'"{o.get("content", "")}"'
        )
    print(f"Total: {result['stale_count']} stale, {result['total_raw']} raw")


def cmd_friction(args):
    """Failures mapped to project boundaries."""
    results = synthesis.friction()

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No failures mapped to project boundaries.")
        return

    for r in results:
        error_strs = [f"{et}: {count}" for et, count in r["error_types"].items()]
        print(
            f"  {r['boundary']} boundary: {r['failure_count']} failures "
            f"({', '.join(error_strs)})"
        )


def cmd_blind_spots(args):
    """Recurring failures without journal entries."""
    result = synthesis.blind_spots(threshold=args.threshold)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    orphaned = result["orphaned_failures"]
    if not orphaned:
        print("No blind spots detected.")
        return

    print("Blind spots (failures without nearby decisions):")
    for o in orphaned:
        first = o["first_occurrence"][:10]
        latest = o["latest_occurrence"][:10]
        print(f"  {o['error_type']}: {o['count']} failures")
        print(f"    First: {first}, Latest: {latest}")
    print(f"Total: {result['blind_spot_count']} blind spots")


def cmd_refinement(args):
    """Decisions ripe for promotion to patterns."""
    result = synthesis.refinement(
        min_cluster=args.min_cluster,
        stale_days=args.stale_days,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    total = result["cluster_count"] + result["chain_count"] + result["aging_count"]
    if total == 0:
        print("No refinement opportunities found.")
        return

    print("Refinement Opportunities:")

    if result["tag_clusters"]:
        print()
        print("Tag Clusters (unrefined themes):")
        for tc in result["tag_clusters"]:
            print(f"  {tc['tag']}: {tc['decision_count']} decisions, no pattern")
            print(f"    Suggestion: {tc['suggestion']}")

    if result["decision_chains"]:
        print()
        print("Decision Chains (revisited topics):")
        for dc in result["decision_chains"]:
            chain_str = " → ".join(dc["decisions"][:4])
            if dc["chain_size"] > 4:
                chain_str += f" (+{dc['chain_size'] - 4} more)"
            print(f"  {chain_str} ({dc['chain_size']} decisions)")
            if dc["topic"]:
                print(f"    Topic: {dc['topic']}")

    if result["aging"]:
        print()
        print("Aging Decisions (unresolved):")
        for a in result["aging"]:
            print(
                f"  {a['id']}  {a['timestamp']}  "
                f'"{a["decision"]}" ({a["age_days"]} days, {a["outcome"]})'
            )

    print()
    print(
        f"Summary: {result['cluster_count']} clusters, "
        f"{result['chain_count']} chains, "
        f"{result['aging_count']} aging decisions"
    )


def cmd_context(args):
    """Filtered context brief for agent prompts."""
    result = synthesis.context(
        tags=args.tags,
        project=args.project,
        since_days=args.since_days,
        budget=args.budget,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    debug = args.debug

    # Build header
    parts = []
    if args.tags:
        parts.append(f"tags={','.join(args.tags)}")
    if args.project:
        parts.append(f"project={args.project}")
    if args.since_days:
        parts.append(f"since={args.since_days}d")
    header = f"Context: {' '.join(parts)}" if parts else "Context: (all)"
    print(header)

    def _score_suffix(item):
        if debug:
            return f"  [{item.get('_score', 0)}]"
        return ""

    if result["evidence"]:
        print()
        print("Evidence:")
        for e in result["evidence"]:
            conf = e.get("confidence", "preliminary")
            print(f"  {e['id']}  [{conf}]  {e['content']}{_score_suffix(e)}")
            if e.get("source"):
                print(f"    Source: {e['source']}")
            if e.get("provenance"):
                print(f"    Provenance: {e['provenance']}")

    if result["patterns"]:
        print()
        print("Patterns:")
        for p in result["patterns"]:
            conf = p.get("confidence", 0)
            print(f"  {p['name']}{_score_suffix(p)}")
            if p.get("solution"):
                # Wrap long solutions
                sol = p["solution"]
                if len(sol) > 72:
                    words = sol.split()
                    lines = []
                    line = ""
                    for w in words:
                        if line and len(line) + len(w) + 1 > 68:
                            lines.append(line)
                            line = w
                        else:
                            line = f"{line} {w}" if line else w
                    if line:
                        lines.append(line)
                    for ln in lines:
                        print(f"    {ln}")
                else:
                    print(f"    {sol}")
                print(f"    (confidence: {conf})")

    if result["anti_patterns"]:
        print()
        print("Anti-patterns:")
        for a in result["anti_patterns"]:
            print(f"  {a['name']}{_score_suffix(a)}")
            if a.get("risk"):
                print(f"    Risk: {a['risk']}")
            if a.get("fix"):
                print(f"    Fix: {a['fix']}")

    if result["decisions"]:
        print()
        print("Decisions:")
        for d in result["decisions"]:
            outcome = f" ({d['outcome']})" if d.get("outcome") else ""
            print(f"  {d['id']}  {d['decision']}{outcome}{_score_suffix(d)}")
            if d.get("rationale"):
                print(f"    Rationale: {d['rationale']}")

    if result["goals"]:
        print()
        print("Goals:")
        for g in result["goals"]:
            print(
                f"  {g['id']}  {g['name']} [{g.get('status', '?')}]{_score_suffix(g)}"
            )
            for sc in g.get("success_criteria", []):
                print(f"    - {sc}")

    if result.get("contentions"):
        print()
        print("Contentions:")
        for c in result["contentions"]:
            print(f"  {c['tag']}: {c['a']} vs {c['b']} ({c['outcomes']})")

    if not any(
        [
            result["evidence"],
            result["patterns"],
            result["anti_patterns"],
            result["decisions"],
            result["goals"],
        ]
    ):
        print()
        print("(no matching items)")

    gt = result.get("ground_truth")
    if gt:
        print()
        print(f"Ground Truth: {gt['verification'].upper()}")
        cov = gt.get("coverage") or {}
        if cov:
            print(
                f"  Coverage: {cov.get('passing', 0)} passing, "
                f"{cov.get('failing', 0)} failing, "
                f"{cov.get('untested', 0)} untested"
            )
        if gt.get("orphan_count", 0) > 0:
            print(f"  Orphans: {gt['orphan_count']}")

    print()
    trunc = " (truncated)" if result["truncated"] else ""
    print(f"~{result['token_estimate']} tokens{trunc}")


def cmd_overlap(args):
    """Command name conflicts across projects."""
    results = synthesis.ecosystem_overlap()

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No command name conflicts found.")
        return

    print("Command Name Conflicts:")
    for o in results:
        projs = ", ".join(o["projects"])
        print(f"  `{o['command']}` — {projs}")
    print()
    print("Fix: Rename or consolidate commands in owning project")


def cmd_complexity(args):
    """Projects exceeding complexity thresholds."""
    results = synthesis.ecosystem_complexity(
        max_commands=args.max_commands,
        max_options=args.max_options,
    )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No projects exceed complexity thresholds.")
        return

    print("Complexity Warnings:")
    for c in results:
        print(
            f"  {c['project']}: {c['command_count']} commands "
            f"(threshold: {c['threshold']})"
        )
    print()
    print("Fix: Group related commands under subcommands, remove rarely-used options")


def cmd_undocumented(args):
    """Decisions and patterns lacking rationale."""
    result = synthesis.undocumented()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if not result["decisions"] and not result["patterns"]:
        print("All decisions and patterns are documented.")
        return

    print("Undocumented:")
    for d in result["decisions"]:
        print(f'  {d["id"]}: "{d["decision"]}" (no rationale)')
    for p in result["patterns"]:
        missing = ", ".join(p["missing"])
        print(f'  {p["id"]}: "{p["name"]}" (missing: {missing})')
    print()
    if result["decisions"]:
        print('Fix: lore remember "<decision>" --rationale "why"')
    if result["patterns"]:
        print('Fix: lore learn "<pattern>" --problem "what it solves"')


def cmd_drift(args):
    """Decision reversals over time."""
    result = synthesis.drift(
        tags=args.tags,
        project=args.project,
        since_days=args.since_days,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if result["reversal_count"] == 0 and result["chain_count"] == 0:
        print("No decision reversals found.")
        return

    if result["reversals"]:
        print("Reversals:")
        for r in result["reversals"]:
            rev = r["revised"]
            ts = rev["timestamp"][:10]
            print(f'  {rev["id"]}  {ts}  "{rev["title"]}"')
            rep = r["replaced_by"]
            if rep:
                rep_ts = rep["timestamp"][:10]
                print(
                    f'    -> {rep["id"]}  {rep_ts}  "{rep["title"]}" ({rep["outcome"]})'
                )
            else:
                print("    -> (no replacement linked)")

    if result["volatile_tags"]:
        print()
        print("Volatile Tags:")
        for vt in result["volatile_tags"]:
            print(f"  {vt['tag']}: {vt['reversal_count']} reversals")

    if result["chains"]:
        print()
        print("Revision Chains:")
        for chain in result["chains"]:
            steps = chain["steps"]
            parts = []
            for s in steps:
                marker = "~" if s["outcome"] == "revised" else ""
                parts.append(f"{marker}{s['id']}")
            print(f"  {' -> '.join(parts)}")
            for s in steps:
                ts = s["timestamp"][:10]
                outcome = f" ({s['outcome']})" if s["outcome"] else ""
                print(f'    {s["id"]}  {ts}  "{s["title"]}"{outcome}')

    print()
    print(
        f"Summary: {result['reversal_count']} reversals, {result['chain_count']} chains"
    )


def cmd_correlate(args):
    """Failures alongside nearby decisions."""
    results = synthesis.correlate(window_hours=args.window)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print("No failures recorded.")
        return

    for r in results:
        f = r["failure"]
        ts = f.get("timestamp", "")[:16].replace("T", " ")
        print(
            f"  {ts}  {f.get('id', '?')}  {f.get('error_type', '?')} -- "
            f"{f.get('error_message', '')}"
        )
        for d in r["nearby_decisions"]:
            print(f'    nearby: {d.get("id", "?")} "{d.get("decision", "")}"')


# --- Delegation commands (pass through to Lore) ---


def cmd_fail(args):
    """Delegate to lore fail."""
    cmd = ["lore", "fail", args.error_type, args.message]
    subprocess.run(cmd)


def cmd_observe(args):
    """Delegate to lore observe."""
    subprocess.run(["lore", "observe", args.text])


def cmd_decide(args):
    """Delegate to lore remember."""
    subprocess.run(["lore", "remember", args.text])


def cmd_impact(args):
    """Blast radius across the ecosystem."""
    projects = args.projects if hasattr(args, "projects") and args.projects else None
    result = synthesis.impact_view(args.base, args.head, projects)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    blast = result["blast"]
    risk = blast["risk_level"].upper()
    score = blast["risk_score"]
    print(f"Risk: {risk} ({score})")
    print()

    changed = result["changed_files"]
    if changed:
        total = sum(len(v) for v in changed.values())
        print(f"Changed Files ({total}):")
        for proj, files in sorted(changed.items()):
            for f in files:
                print(f"  [{proj}] {f}")
        print()

    reqs = blast["affected_requirements"]
    if reqs:
        print(f"Affected Requirements ({len(reqs)}):")
        for r in reqs:
            print(f"  {r}")
        print()

    modules = blast["affected_modules"]
    if modules:
        print(f"Affected Modules ({len(modules)}):")
        for m in modules:
            print(f"  {m}")
        print()

    edges = result["edge_summary"]
    print(
        f"Edges: {edges['annotated']} annotated, "
        f"{edges['inferred']} inferred, {edges['contract']} contract"
    )

    recs = result.get("recommendations", [])
    if recs:
        print()
        print("Recommendations:")
        for r in recs:
            print(f"  - {r}")


def cmd_fleet(args):
    """Fleet status synthesized by intervention severity."""
    result = synthesis.fleet_view()

    if args.json:
        print(json.dumps(result, indent=2))
        return

    status_val = result["status"].upper()
    print(f"Fleet: {status_val}")

    if result["status"] == "unavailable":
        print("  fleet.db not found.")
        return

    counts = result["counts"]

    # --- Critical ---
    if result["violations"]:
        print()
        print(f"Violations ({counts['violations']}):")
        for v in result["violations"]:
            code = v.get("code", "?")
            msg = v.get("message", "")
            subj = v.get("subject_id", "?")
            print(f"  {code}: {msg} ({subj})")

    if result["scope_overlap"]:
        print()
        print(f"Scope Overlap ({counts['scope_overlap']}):")
        # Group by task pair
        pairs: dict[tuple, list] = {}
        for o in result["scope_overlap"]:
            key = (o.get("task_id_a", "?"), o.get("task_id_b", "?"))
            pairs.setdefault(key, []).append(o.get("shared_file", "?"))
        for (a, b), files in pairs.items():
            print(f"  {a} <-> {b}: {', '.join(files)}")

    # --- Attention ---
    if result["expired_leases"]:
        print()
        print(f"Expired Leases ({counts['expired_leases']}):")
        for e in result["expired_leases"]:
            mins = e.get("minutes_overdue", 0)
            tid = e.get("task_id", "?")
            agent = e.get("claimed_by", "?")
            print(f"  {tid} claimed by {agent} ({mins:.0f}m overdue)")

    if result["rule_of_three"]:
        print()
        print(f"Rule of Three ({counts['rule_of_three']}):")
        for r in result["rule_of_three"]:
            sig = r.get("signature", "?")
            agent = r.get("agent_id", "?")
            n = r.get("occurrence_count", 0)
            print(f"  {sig} ({agent}): {n}x in last hour")

    if result["blind_spots"]:
        print()
        print(f"Blind Spots ({counts['blind_spots']}):")
        for b in result["blind_spots"]:
            sig = b.get("signature") or b.get("error_type", "?")
            n = b.get("occurrences", 0)
            print(f"  {sig}: {n} failures, no intervention")

    # --- Active ---
    agents = result["agents"]
    print()
    print(f"Agents: {counts['agents']} active")
    if agents:
        for a in agents:
            role = a.get("role", "?")
            model = a.get("model", "?")
            print(f"  {a.get('agent_id', '?')} [{role}] ({model})")

    task_counts = result["tasks"]
    if task_counts:
        print()
        print("Tasks:")
        for st, count in sorted(task_counts.items()):
            print(f"  {st}: {count}")

    if result["merge_queue"]:
        print()
        print(f"Merge Queue ({counts['merge_queue']}):")
        for t in result["merge_queue"]:
            branch = t.get("branch", "")
            suffix = f" ({branch})" if branch else ""
            tid = t.get("task_id", "?")
            st = t.get("status")
            title = t.get("title", "")
            print(f"  {tid} [{st}] {title}{suffix}")

    # --- Cost ---
    if result["token_summary"]:
        print()
        print("Token Usage:")
        for t in result["token_summary"]:
            agent = t.get("agent_id", "?")
            model = t.get("model", "?")
            total = t.get("total_tokens", 0)
            print(f"  {agent} ({model}): {total:,} tokens")


def main():
    parser = argparse.ArgumentParser(
        prog="praxis",
        description="Pragmatic leverage for getting shit done",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- Operational commands --

    p = sub.add_parser("status", help="Where am I? Active goals, blockers")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", help="What should I work on now?")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("blockers", help="Failures, stale signals, friction")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_blockers)

    p = sub.add_parser("health", help="Ecosystem health summary")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("context", help="Filtered context brief for agent prompts")
    p.add_argument("--tags", nargs="+", help="Filter by tags")
    p.add_argument("--project", help="Filter by project name")
    p.add_argument(
        "--since", type=int, dest="since_days", help="Days of recency (default: all)"
    )
    p.add_argument(
        "--budget", type=int, default=2000, help="Token budget (default: 2000)"
    )
    p.add_argument("--debug", action="store_true", help="Show relevance scores")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("verify", help="Ground-truth verification against code")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_verify)

    # -- Analysis commands --

    p = sub.add_parser("triggers", help="Error types hitting Rule of Three")
    p.add_argument(
        "--threshold", type=int, default=3, help="Trigger count (default: 3)"
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_triggers)

    p = sub.add_parser("stale", help="Signals aging without action")
    p.add_argument("--days", type=int, default=7, help="Age threshold (default: 7)")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_stale)

    p = sub.add_parser("friction", help="Failures mapped to project boundaries")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_friction)

    p = sub.add_parser("blind-spots", help="Recurring failures without journal entries")
    p.add_argument(
        "--threshold", type=int, default=3, help="Failure count threshold (default: 3)"
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_blind_spots)

    p = sub.add_parser("refinement", help="Decisions ripe for promotion to patterns")
    p.add_argument(
        "--min-cluster", type=int, default=3, help="Tag cluster threshold (default: 3)"
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=14,
        help="Aging threshold in days (default: 14)",
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_refinement)

    p = sub.add_parser("overlap", help="Command name conflicts across projects")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_overlap)

    p = sub.add_parser("complexity", help="Projects exceeding complexity thresholds")
    p.add_argument(
        "--max-commands",
        type=int,
        default=10,
        help="Command count threshold (default: 10)",
    )
    p.add_argument(
        "--max-options",
        type=int,
        default=5,
        help="Options per command threshold (default: 5)",
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_complexity)

    p = sub.add_parser("undocumented", help="Decisions and patterns lacking rationale")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_undocumented)

    p = sub.add_parser("drift", help="Decision reversals over time")
    p.add_argument("--tags", nargs="+", help="Filter by tags")
    p.add_argument("--project", help="Filter by project name")
    p.add_argument(
        "--since", type=int, dest="since_days", help="Days of recency (default: all)"
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_drift)

    p = sub.add_parser("correlate", help="Failures alongside nearby decisions")
    p.add_argument("--window", type=int, default=24, help="Hours (default: 24)")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_correlate)

    # -- Delegation commands --

    p = sub.add_parser("fail", help="Log a failure (delegates to lore)")
    p.add_argument("error_type", help="Error category (Timeout, NonZeroExit, etc)")
    p.add_argument("message", help="What happened")
    p.set_defaults(func=cmd_fail)

    p = sub.add_parser("observe", help="Capture observation (delegates to lore)")
    p.add_argument("text", help="Observation text")
    p.set_defaults(func=cmd_observe)

    p = sub.add_parser("decide", help="Record decision (delegates to lore)")
    p.add_argument("text", help="Decision text")
    p.set_defaults(func=cmd_decide)

    # -- Watchdog commands --

    p = sub.add_parser("watchdog", help="Run watchdog to monitor command failures")
    p.add_argument("--cmd", required=True, help="Command to run")
    p.add_argument("--project", required=True, help="Project name")
    p.add_argument("--window", default="10m", help="Time window (e.g. 10m, 600s)")
    p.add_argument(
        "--threshold", type=int, default=3, help="Failures required to trigger"
    )
    p.add_argument("--interval", default="5m", help="Interval between runs")
    p.set_defaults(func=cmd_watchdog)

    p = sub.add_parser("watchdog-report", help="Summary of recent watchdog failures")
    p.set_defaults(func=cmd_watchdog_report)

    # -- Impact commands --

    p = sub.add_parser("impact", help="Blast radius across ecosystem")
    p.add_argument("--base", default="HEAD~1", help="Base ref (default: HEAD~1)")
    p.add_argument("--head", default="HEAD", help="Head ref (default: HEAD)")
    p.add_argument("--projects", nargs="+", help="Filter to specific projects")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_impact)

    # -- Fleet commands --

    p = sub.add_parser("fleet", help="Fleet status: agents, tasks, merge queue")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_fleet)

    args = parser.parse_args()

    try:
        args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
