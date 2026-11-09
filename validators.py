def is_relevant(item, keywords, match_all=False):
    text = f"{item.get('title', '')} {item.get('url', '')} {item.get('snippet', '')}".lower()
    checks = [word.lower() in text for word in keywords if word]

    if not checks:
        return False
    return all(checks) if match_all else any(checks)


def validate_web_results(result, keywords, match_all=False):
    if result.get("status") != "ok":
        return result

    all_items = result.get("results", [])
    good_items = [item for item in all_items if is_relevant(item, keywords, match_all)]
    removed = len(all_items) - len(good_items)

    checked = dict(result)
    checked["results"] = good_items

    if not good_items:
        checked["status"] = "no_data"
        checked["message"] = "Web results were found, but none were relevant to this trip."
    else:
        checked["message"] = (
            f"{len(good_items)} relevant web result(s) kept, {removed} removed."
        )

    return checked