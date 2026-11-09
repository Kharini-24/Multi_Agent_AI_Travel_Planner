TYPE_LABELS = {"web_search": "web search", "assumption": "assumption"}


def flights_section(result):
    lines = [
        "### ✈️ Flights",
        "*Source: live API data (AviationStack). No prices or availability.*",
        "",
    ]
    if result.get("status") != "ok":
        lines.append(f"Live flight data not available: {result.get('message', 'no data')}")
    else:
        for f in result["flights"]:
            lines.append(f"- {f['airline']} {f['flight_number']}")
        lines.append("")
        lines.append(
            "These flights appeared in recent live data. This is not a timetable, "
            "so check the airline's website for dates and times."
        )
    return "\n".join(lines)


def _web_section(title, source_note, result, empty_text):
    lines = [title, f"*{source_note}*", ""]
    if result.get("status") != "ok":
        lines.append(f"{empty_text} ({result.get('message', 'no data')})")
    else:
        for r in result["results"]:
            name = r["title"].replace("[", "(").replace("]", ")")
            lines.append(f"- [{name}]({r['url']})")
    return "\n".join(lines)


def fares_section(result):
    return _web_section(
        "### 🎫 Flight fares",
        "Source: web search (Tavily). These are advertised 'from' prices, not a quote.",
        result,
        "Fare information not available",
    )


def hotels_section(result):
    return _web_section(
        "### 🏨 Hotels",
        "Source: web search (Tavily). Prices and availability must be confirmed on the website.",
        result,
        "Hotel information not available",
    )


def budget_section(report):
    lines = [
        "### 💰 Budget check",
        "*Source: estimate calculated by our code from the cheapest advertised prices "
        "plus fixed assumptions. It is a minimum, not a quote.*",
        "",
    ]
    if report.get("lines"):
        lines.append("| Item | Estimate | Based on |")
        lines.append("|---|---|---|")
        for line in report["lines"]:
            basis = TYPE_LABELS.get(line["type"], line["type"])
            lines.append(
                f"| {line['item']} | ₹{line['amount']:,} | {basis}: {line['note']} |"
            )
        if report.get("total") is not None:
            lines.append(f"| **Total** | **₹{report['total']:,}** | |")
        lines.append("")
    lines.append(report.get("message") or "No budget information.")
    return "\n".join(lines)