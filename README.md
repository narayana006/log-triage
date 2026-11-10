# log-triage

Collapse noisy logs into patterns, surface what is new or spiking, and summarise the likely cause.

> **Project status: planning. There is no working code in this repository yet.**
> This README describes what the project will do. Nothing below can be installed or run today.
> Features are ticked off in the checklist as they are built.

## What it is

A command-line tool.

**The problem it solves:** During an incident the signal is buried in millions of repeated log lines.

## Who it is for

Engineers reading logs during an incident or investigation.

## How it will work

1. You pipe logs into the tool, optionally with a baseline from a normal period.
2. It collapses repeated lines into patterns and counts them.
3. It shows which patterns are new or spiking and summarises the most likely cause with example lines.

## Planned features

Unticked items are not built yet.

- [ ] Reads logs from stdin, files or a log backend
- [ ] Clusters lines into templates with counts
- [ ] Highlights patterns that are new or spiking compared with a baseline window
- [ ] Short summary of the most likely cause with example lines
- [ ] Works offline for the clustering step

## Planned usage

This is the intended interface, shown so you can judge the design. **It does not work yet**, and names may change before the first release.

```bash
kubectl logs deploy/api --since=1h | log-triage --baseline yesterday.log
```

## Contributing

Feedback on the design is the most useful contribution right now. Open an issue to suggest a feature, question an approach or describe your use case. Code contributions are welcome once the first version lands.

## License

[MIT](LICENSE)
