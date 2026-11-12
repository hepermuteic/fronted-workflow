"""Check declared and actually rendered body fonts in fixed browser evidence."""

import re
import unicodedata


def is_yahei(value):
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    compact = re.sub(r"[\s_\-\"']", "", text)
    return "microsoftyahei" in compact or "微软雅黑" in compact


def source_findings(text):
    problems = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selectors, declarations = match.groups()
        selectors = selectors.rsplit(">", 1)[-1]
        body_selector = any(
            re.fullmatch(
                r"(?:html|body|p|li|label|input|textarea|button|output)(?:[.#][\w-]+)*",
                selector.strip(),
                re.I,
            )
            for selector in selectors.split(",")
        )
        family = re.search(
            r"(?:^|;)\s*font(?:-family)?\s*:\s*([^;]+)", declarations, re.I
        )
        if body_selector and family and is_yahei(family[1]):
            problems.append(
                "Forbidden body font Microsoft YaHei in an explicit body-text rule"
            )
    return problems


def findings(snapshot):
    failures, gaps = [], []
    report = snapshot.get("body_typography")
    if not isinstance(report, dict):
        return [], [
            "Actual body font inspection is missing; recapture with the current runner"
        ]
    for sample in report.get("samples", []):
        location = sample.get("selector", "body text")
        if is_yahei(sample.get("font_family", "")):
            failures.append(
                "Forbidden body font Microsoft YaHei in the selected stack at "
                + location
            )
        for font in sample.get("fonts", []):
            if font.get("glyphCount", 0) > 0 and (
                is_yahei(font.get("familyName", ""))
                or is_yahei(font.get("postScriptName", ""))
            ):
                failures.append(
                    "Forbidden body font Microsoft YaHei actually rendered at "
                    + location
                )
    if report.get("status") != "verified" or report.get("errors"):
        gaps.extend(
            "Body typography unverified: " + str(error)
            for error in report.get("errors", [])
        )
        if not report.get("errors"):
            gaps.append("Actual body typography remains unverified")
    return list(dict.fromkeys(failures)), list(dict.fromkeys(gaps))
