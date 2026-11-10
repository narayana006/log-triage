# log-triage

Collapse noisy logs into patterns and see which ones are new or spiking compared with a normal period.

**Status: early but working (v0.1.0).** Templating, pattern counts, baseline comparison (new and spiking patterns), a "where to look first" pointer, text and JSON output all work today, fully offline. Reading directly from a log backend is not built yet.

## Why

During an incident the signal is buried under thousands of repeated lines that differ only in a timestamp, a request id or a duration. `log-triage` masks the parts that vary, so those lines collapse into a handful of patterns, and then answers the question you actually have: *what is in these logs that was not there yesterday?*

## Install

Python 3.10 or newer. No runtime dependencies.

```bash
git clone https://github.com/narayana006/log-triage
cd log-triage
pip install .
```

## Quick start

The repository ships a sample incident log and a baseline from a quiet period:

```bash
log-triage examples/incident.log --baseline examples/baseline.log
```

```text
400 lines -> 10 patterns  (baseline: 600 lines, 7 patterns)

NEW - not seen in baseline (3)
      87  ERROR  <TS> ERROR api-<HEX>-<ID> db: connection to <IP>:<NUM> timed out after <NUM>ms
                 e.g. 2024-05-14T14:01:02.032Z ERROR api-7d9f5c8b46-m8n3p db: connection to 10.0.3.205:5432 timed out after 5325ms
      26  ERROR  <TS> ERROR api-<HEX>-<ID> http: POST /api/v1/orders <NUM> request_id=<UUID> upstream unavailable
                 e.g. 2024-05-14T14:01:01.055Z ERROR api-7d9f5c8b46-q7w2e http: POST /api/v1/orders 503 request_id=f1c475d7-0c0a-97b3-7924-e06f44afcdc8 upstream unavailable
      10  WARN   <TS> WARN api-<HEX>-<ID> pool: connection pool exhausted (<NUM>/<NUM> in use), <NUM> waiters
                 e.g. 2024-05-14T14:00:52.386Z WARN  api-7d9f5c8b46-x2k4q pool: connection pool exhausted (49/50 in use), 80 waiters

SPIKING - share of lines grew vs baseline (1)
      33  WARN   <TS> WARN api-<HEX>-<ID> pool: retrying checkout attempt <NUM> of <NUM>
                 x12.4 share of lines (baseline count 4)
                 e.g. 2024-05-14T14:00:21.995Z WARN  api-7d9f5c8b46-m8n3p pool: retrying checkout attempt 1 of 5

TOP PATTERNS (10 of 10)
      95  INFO   <TS> INFO api-<HEX>-<ID> cache: refreshed <NUM> keys in <NUM>ms
      87  ERROR  <TS> ERROR api-<HEX>-<ID> db: connection to <IP>:<NUM> timed out after <NUM>ms
      44  INFO   <TS> INFO api-<HEX>-<ID> http: GET /healthz <NUM> <NUM>ms request_id=<UUID>
      41  INFO   <TS> INFO api-<HEX>-<ID> http: GET /api/v1/users <NUM> <NUM>ms request_id=<UUID>
      39  INFO   <TS> INFO api-<HEX>-<ID> http: GET /api/v1/orders <NUM> <NUM>ms request_id=<UUID>
      33  WARN   <TS> WARN api-<HEX>-<ID> pool: retrying checkout attempt <NUM> of <NUM>
      26  ERROR  <TS> ERROR api-<HEX>-<ID> http: POST /api/v1/orders <NUM> request_id=<UUID> upstream unavailable
      21  DEBUG  <TS> DEBUG api-<HEX>-<ID> auth: token for user <NUM> validated
      10  WARN   <TS> WARN api-<HEX>-<ID> pool: connection pool exhausted (<NUM>/<NUM> in use), <NUM> waiters
       4  WARN   <TS> WARN api-<HEX>-<ID> http: slow request GET /api/v1/users took <NUM>ms

WHERE TO LOOK FIRST
  Earliest changed warning/error (input line 122, 10 lines):
    2024-05-14T14:00:52.386Z WARN  api-7d9f5c8b46-x2k4q pool: connection pool exhausted (49/50 in use), 80 waiters
  Most frequent changed warning/error (87 lines):
    2024-05-14T14:01:02.032Z ERROR api-7d9f5c8b46-m8n3p db: connection to 10.0.3.205:5432 timed out after 5325ms
  Heuristic only: earliest is often the trigger, most frequent the symptom.
```

Four hundred lines became ten patterns; three of them never appear in the baseline, and one that does appear went from 4 lines to 33.

## Usage

```text
log-triage [FILES ...] [--baseline FILE] [--top N] [--spike-ratio R]
           [--min-count N] [--examples N] [--json] [--fail-on-new]
```

Logs come from the files you name, or from stdin when you name none (`-` also means stdin):

```bash
kubectl logs deploy/api --since=1h | log-triage --baseline yesterday.log
journalctl -u api --since "1 hour ago" | log-triage
log-triage app.log.1 app.log --top 20
```

Without `--baseline` you get the pattern counts only. With it you also get the NEW, SPIKING and WHERE TO LOOK FIRST sections.

| Option | Default | Meaning |
| --- | --- | --- |
| `-b`, `--baseline FILE` | none | Log file from a normal period to compare against. |
| `--top N` | 10 | Patterns shown per section. |
| `--spike-ratio R` | 3.0 | How many times a pattern's share of lines must grow to count as spiking. |
| `--min-count N` | 5 | Patterns with fewer lines than this are never reported as spiking. |
| `--examples N` | 1 | Raw example lines shown under each new or spiking pattern. |
| `--json` | off | Machine-readable output with the same information. |
| `--fail-on-new` | off | Exit 1 if anything is new or spiking (for scripts and CI). |

Exit codes: `0` success, `1` new or spiking patterns found with `--fail-on-new`, `2` bad arguments, unreadable file or empty input.

### How lines become patterns

Each line is rewritten by a fixed list of rules, most specific first:

| Placeholder | Replaces |
| --- | --- |
| `<TS>` | ISO 8601, syslog and access-log timestamps, bare `HH:MM:SS` |
| `<UUID>` | UUIDs |
| `<EMAIL>` | e-mail addresses |
| `<IP>` | IPv4 addresses |
| `<HEX>` | `0x...` values and bare hex strings of 8+ characters |
| `<ID>` | mixed letter/digit tokens of 5+ characters with at least two digits (request ids, pod suffixes) |
| `<NUM>` | remaining numbers, including ones with a unit suffix (`<NUM>ms`) |

Digits inside a word are left alone, so `v2`, `http2` and `oauth2` stay readable.

### How "spiking" is decided

Counts are compared as a *share of all lines*, not as raw numbers, so a one-hour window can be compared against a full day of baseline. A pattern is spiking when its share grew by at least `--spike-ratio` and it has at least `--min-count` lines. Any pattern that is absent from the baseline is new, even if it occurs once.

### Where to look first

A heuristic, not root-cause analysis. Among new and spiking patterns at WARN level or above it shows the new pattern that appeared earliest in the input (often the trigger) and the one with the most lines (usually the main symptom). The log level is taken from the first level keyword on the line (`ERROR`, `warn`, `level=error`, ...).

## Features

- [x] Reads logs from stdin and files
- [ ] Reads logs from a log backend (Loki, CloudWatch, Elasticsearch)
- [x] Clusters lines into templates with counts
- [x] Highlights patterns that are new or spiking compared with a baseline
- [x] Rule-based pointer to the likely cause, with example lines
- [ ] Written natural-language summary of the likely cause
- [x] Works offline (everything shipped today does)
- [x] JSON output and `--fail-on-new` exit code

## Limitations

- Templating is a fixed set of regular expressions, not a learned parser. Variable *words* (user names, free-text error details) are not masked, so such lines stay as separate patterns.
- The `<ID>` rule can over-mask ordinary tokens with two or more digits, such as `sha256` or `base64`.
- IPv6 addresses are not recognised as a unit.
- Structured (JSON) log lines are treated as plain text; fields are not parsed.
- Multi-line entries such as stack traces are treated one line at a time.
- All patterns are held in memory. That is fine for millions of lines with a normal number of distinct patterns, but there is no cap.
- The baseline must be a raw log file; saving and reusing a pre-computed baseline is not supported yet.

## Contributing

Issues and pull requests are welcome, especially log samples that template badly. To work on the code:

```bash
pip install -e ".[dev]"
pytest
```

Built and maintained by [Narayana Vemburaj](https://github.com/narayana006).

## License

[MIT](LICENSE)
