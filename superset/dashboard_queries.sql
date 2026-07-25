-- ═══════════════════════════════════════════════════════════════
-- AI Gateway — Superset Dashboard Queries (Phase 2)
-- Connect Superset to the PostgreSQL `gateway` database, then
-- create one chart per query below.
-- ═══════════════════════════════════════════════════════════════

-- ── Chart 1: Total Estimated Spend per User (last 30 days) ────
SELECT
    u.email,
    SUM(r.estimated_cost_usd)   AS total_cost_usd,
    COUNT(*)                    AS request_count,
    SUM(r.total_tokens)         AS total_tokens
FROM request_logs r
JOIN users u ON u.id = r.user_id
WHERE r.created_at >= NOW() - INTERVAL '30 days'
  AND r.was_cached = FALSE
GROUP BY u.email
ORDER BY total_cost_usd DESC;


-- ── Chart 2: Average Latency by Model (last 7 days) ───────────
SELECT
    model_used,
    ROUND(AVG(total_latency_ms)::numeric, 2)  AS avg_latency_ms,
    ROUND(AVG(ttft_ms)::numeric, 2)           AS avg_ttft_ms,
    COUNT(*)                                  AS request_count
FROM request_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND status_code = 200
GROUP BY model_used
ORDER BY avg_latency_ms;


-- ── Chart 3: Error Rate by Status Code (last 24 hours) ────────
SELECT
    status_code,
    COUNT(*)                                           AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM request_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY status_code
ORDER BY count DESC;


-- ── Chart 4: Cache Hit Rate Over Time (hourly buckets) ────────
SELECT
    DATE_TRUNC('hour', created_at)   AS hour,
    COUNT(*) FILTER (WHERE was_cached = TRUE)  AS cache_hits,
    COUNT(*) FILTER (WHERE was_cached = FALSE) AS cache_misses,
    ROUND(
        COUNT(*) FILTER (WHERE was_cached = TRUE) * 100.0 / NULLIF(COUNT(*), 0),
        1
    ) AS hit_rate_pct
FROM request_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1;


-- ── Chart 5: Guardrail Interception Rates ─────────────────────
SELECT
    DATE_TRUNC('day', created_at)  AS day,
    COUNT(*) FILTER (WHERE input_guardrail_action  = 'blocked')  AS input_blocks,
    COUNT(*) FILTER (WHERE output_guardrail_action = 'redacted') AS output_redactions,
    COUNT(*)                                                      AS total_requests
FROM request_logs
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
