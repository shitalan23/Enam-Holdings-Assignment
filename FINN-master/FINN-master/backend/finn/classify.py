"""Announcement classifier v2: label-first, confidence-scored, with an explicit "Needs review".

Why v1 failed: it searched the whole filing text for broad keywords and let the body outvote
the exchange's own label. A newspaper ad *about* results, or an invitation to a call *about*
results, contains "financial results ... quarter ended" and was filed under Results.

How v2 decides, in order:
  1. The NSE label (the `desc` field) is a controlled vocabulary, so it is the primary signal.
     Matching is anchored to the label, not scattered across the body.
  2. The body only (a) resolves *generic* labels such as "Outcome of Board Meeting" or "Updates",
     and (b) picks the subtype (e.g. transcript vs. call notice). It never overrides a specific label.
  3. Every decision carries a confidence and a reason. Below MIN_CONFIDENCE the result becomes
     `needs_review` and the best guess is kept in the reason string for a human to check.
"""
import re
from dataclasses import dataclass

I = re.IGNORECASE
MIN_CONFIDENCE = 0.6

TAXONOMY = {
    "results": "Results",
    "investor_events": "Calls & investor events",
    "management_change": "Management change",
    "m_and_a": "M&A",
    "board_meeting": "Board meeting",
    "corporate_action": "Dividends & corporate actions",
    "fund_raise": "Fundraising",
    "litigation_regulatory": "Litigation & regulatory",
    "shareholding_change": "Shareholding change",
    "credit_rating": "Credit rating",
    "business_update": "Business update",
    "shareholder_meeting": "Shareholder meeting",
    "routine_compliance": "Routine compliance",
    "other": "Other",
    "needs_review": "Needs review",
}

# Old (v1) keys -> nearest v2 key. Only used to show a before/after table in `reclassify`.
LEGACY_MAP = {
    "M&A": "m_and_a", "fund_raise": "fund_raise", "litigation": "litigation_regulatory",
    "insider_trading": "shareholding_change", "pledging": "shareholding_change",
    "earnings_call": "investor_events", "investor_meetings": "investor_events",
    "dividend": "corporate_action", "bonus_split": "corporate_action", "capex": "business_update",
    "press_release": "business_update", "postal_ballot": "shareholder_meeting",
    "agm_egm": "shareholder_meeting", "unclassified": "routine_compliance",
}


@dataclass
class Classification:
    category: str
    subtype: str | None
    confidence: float
    reason: str
    method: str = "rules-v2"


def R(cat, sub, conf, why) -> Classification:
    return Classification(cat, sub, conf, why)


def clean_label(desc: str) -> str:
    d = re.sub(r"\s+", " ", desc or "").strip()
    # NSE prefixes many labels with the regulation they are filed under.
    d = re.sub(r"^announcement under regulation 30 \(lodr\)\s*[-–—:]*\s*", "", d, flags=I)
    return d


# ---------------------------------------------------------------- body helpers (subtype only)
EXIT = re.compile(r"resign|cessation|cease[sd]?\b|retire|step(ped|ping)? down|demise|relinquish", I)
TOP = re.compile(r"chief (executive|financial|operating|technology|risk|business)|managing director|\bceo\b|\bcfo\b|\bcoo\b|\bcto\b|\bcro\b|chairman|whole[- ]time director", I)
KMP = re.compile(r"company secretary|compliance officer", I)
AUDITOR = re.compile(r"auditor", I)
ESOP = re.compile(r"esop|esos|esps|employee stock|stock option|share based employee|sweat equity", I)
IEPF = re.compile(r"unclaimed|unpaid dividend|iepf|investor education", I)

AGENDA = [  # board-meeting agenda tags, highest-signal first
    ("results", re.compile(r"(un)?audited[^.]{0,60}results|financial results", I)),
    ("fund_raise", re.compile(r"fund ?raising|raising of (funds|capital)|\bqip\b|rights issue|preferential|non-convertible|\bncds?\b|debentures", I)),
    ("m_and_a", re.compile(r"acquisition|merger|amalgamation|scheme of arrangement|demerger", I)),
    ("dividend", re.compile(r"dividend", I)),
    ("buyback", re.compile(r"buy-?back", I)),
]


def _agenda(body: str) -> str | None:
    for tag, rx in AGENDA:
        if rx.search(body):
            return tag
    return None


def _mgmt(body: str, label_is_generic: bool, label: str) -> Classification:
    blob = body if label_is_generic else f"{label}. {body}"
    exit_ = bool(EXIT.search(blob))
    if AUDITOR.search(blob) and not (TOP.search(blob) or KMP.search(blob) or re.search(r"director", blob, I)):
        if exit_:
            return R("management_change", "auditor_exit", 0.85, "auditor resignation (governance signal)")
        return R("routine_compliance", "auditor_change", 0.85, "auditor appointment, usually routine")
    if re.search(r"registrar|share transfer agent|scrutini[sz]er|debenture trustee", blob, I) and not (TOP.search(blob) or KMP.search(blob)):
        return R("routine_compliance", "agent_change", 0.8, "RTA/scrutiniser/trustee change")
    if not blob.strip() or (label_is_generic and not body.strip()):
        return R("management_change", "change", 0.7, "generic management label, no body text")
    level = "top" if TOP.search(blob) else ("kmp" if KMP.search(blob) else "director")
    return R("management_change", f"{level}_{'exit' if exit_ else 'entry'}", 0.92, f"management label; {level} {'exit' if exit_ else 'entry'} from text")


def _rating_sub(blob: str) -> str:
    if re.search(r"downgrad|revised downward|lowered|negative outlook|watch with negative", blob, I):
        return "downgrade"
    if re.search(r"upgrad|revised upward|positive outlook", blob, I):
        return "upgrade"
    if re.search(r"reaffirm|re-affirm|retained|maintained", blob, I):
        return "reaffirm"
    return "assign"


def _pledge_sub(blob: str) -> str | None:
    if re.search(r"invo(k|c)", blob, I):
        return "pledge_invoked"
    if re.search(r"releas|revok", blob, I):
        return "pledge_released"
    if re.search(r"pledge|encumbrance|creation", blob, I):
        return "pledge_created"
    return None


def _investor_sub(body: str) -> str:
    if re.search(r"transcript", body, I):
        return "transcript"
    if re.search(r"audio|video|recording|webcast", body, I):
        return "recording"
    if re.search(r"conference call|earnings call|con\.? call", body, I):
        return "call_notice"
    if re.search(r"schedule|intimation|meeting|meet\b", body, I):
        return "meet_schedule"
    return "update"


# ---------------------------------------------------------------- label rules
ROUTINE = [
    (r"trading window", "trading_window"),
    (r"newspaper (publication|advertisement|ad)\b|copy of newspaper", "newspaper_ad"),
    (r"shareholding pattern", "shareholding_pattern"),
    (r"certificate under sebi|depositories and participants|reg(ulation)?\.? ?74", "certificate"),
    (r"^compliances?\b|secretarial compliance|annual secretarial", "compliance_report"),
    (r"annual report|^reg(ulation)?\.? ?34", "annual_report"),
    (r"integrated filing-? ?governance|corporate governance|code of conduct", "governance"),
    (r"loss of share|duplicate share|share certificate", "share_certificate"),
    (r"related party", "related_party"),
    (r"statement of (deviation|variation)|investor complaints|reg(ulation)?\.? ?(13|40|7\(3\))", "periodic_filing"),
    (r"esop|esos|esps|employee stock|stock option", "esop"),
    (r"business responsibility|\besg\b|sustainability", "esg"),
    (r"change in (registered office|name of)|registered office", "admin_change"),
]


def _by_label(L: str, lab: str, body: str) -> Classification | None:
    # Specific routine labels first, so "Copy of Newspaper Publication" can never become Results.
    if re.search(r"voting results?|e-?voting|scrutini[sz]er'?s? report", L):
        return R("shareholder_meeting", "voting_results", 0.93, "label: voting results")
    for rx, sub in ROUTINE:
        if re.search(rx, L, I):
            return R("routine_compliance", sub, 0.95, f"label: routine ({sub})")

    # Clarifications about price/volume/results are exchange Q&A, not the event itself.
    if re.search(r"clarification|spurt in volume|price movement|reply to", L):
        return R("other", "clarification", 0.85, "label: clarification")

    # --- Results: only labels that ARE the results filing.
    if re.search(r"integrated filing-? ?financial", L):
        return R("results", "integrated", 0.9, "label: integrated filing (financial)")
    if re.search(r"^(financial results?|(un)?audited .*results?|quarterly results?|annual results?|standalone .*results?|consolidated .*results?|results?)\b", L):
        return R("results", "outcome", 0.95, "label: financial results")

    # --- Investor events (calls, presentations, analyst/investor meets)
    if re.search(r"investor presentation|results presentation|^presentation", L):
        return R("investor_events", "presentation", 0.95, "label: investor presentation")
    if re.search(r"analysts?[/ ]*(institutional )?investor|institutional investor|investor meet|earnings call|con(ference)?\.? ?call|transcript|^analyst", L):
        return R("investor_events", _investor_sub(body), 0.93, "label: analyst/investor meet or call")

    # --- Board meetings. Intimation never counts as results; the agenda is kept as a subtype.
    if re.search(r"outcome of board", L):
        return _board_outcome(body)
    if re.search(r"board meeting|intimation of board", L):
        ag = _agenda(body)
        return R("board_meeting", f"intimation_{ag}" if ag else "intimation", 0.93,
                 f"label: board meeting intimation{'; agenda ' + ag if ag else ''}")

    # --- Management
    if re.search(r"change in directors|key managerial|change in management|^(appointment|resignation|cessation|re-?appointment)\b|appointment of|resignation of|cessation of|director|company secretary|compliance officer", L):
        generic = bool(re.search(r"change in directors.*(auditor|registrar|transfer agent)|key managerial", L))
        return _mgmt(body, generic, lab)

    # --- Shareholding (before M&A: "Takeover Regulations" disclosures are not takeovers)
    if re.search(r"takeover regulations|\bsast\b|regulation 29|regulation 31|reg\.? ?(29|31)\b", L):
        sub = _pledge_sub(body) or "sast"
        return R("shareholding_change", sub, 0.9, f"label: SAST disclosure ({sub})")
    if re.search(r"insider trading|reg(ulation)?\.? ?7\b|pit regulations", L):
        return R("shareholding_change", "insider", 0.9, "label: insider trading disclosure")
    if re.search(r"pledge|encumbrance", L):
        return R("shareholding_change", _pledge_sub(f"{lab} {body}") or "pledge_created", 0.92, "label: pledge")

    # --- Credit rating
    if re.search(r"credit rating|^rating", L):
        return R("credit_rating", _rating_sub(f"{lab} {body}"), 0.95, "label: credit rating")

    # --- Corporate actions
    if re.search(r"^dividend|record date|^bonus|sub-?division|stock split|buy-?back|corporate action|capital reduction", L):
        if IEPF.search(body) or IEPF.search(L):
            return R("routine_compliance", "iepf", 0.9, "dividend label but unclaimed/IEPF text")
        sub = ("bonus" if "bonus" in L else "split" if re.search("split|sub-?division", L)
               else "buyback" if "buy" in L else "record_date" if "record" in L else "dividend")
        return R("corporate_action", sub, 0.95, f"label: corporate action ({sub})")

    # --- Fundraising
    if re.search(r"fund ?raising|\bqip\b|rights issue|preferential|non-convertible|\bncds?\b|debenture|commercial paper|issue of securities|issuance|allotment of securities|^allotment", L):
        if ESOP.search(body):
            return R("routine_compliance", "esop", 0.9, "allotment label but ESOP text")
        if not body.strip():
            return R("fund_raise", "issue", 0.55, "allotment label with no text: ESOP is the common case; unsure")
        return R("fund_raise", "issue", 0.88, "label: securities issue")

    # --- M&A
    if re.search(r"open offer", L):
        return R("m_and_a", "open_offer", 0.92, "label: open offer")
    if re.search(r"acquisition|amalgamation|merger|scheme of arrangement|demerger|joint venture|disposal|divest|slump sale|incorporation of|subsidiary", L):
        sub = "minor" if re.search(r"incorporation of|wholly[- ]owned subsidiary.{0,40}incorporat", f"{L} {body}", I) else "deal"
        return R("m_and_a", sub, 0.92, f"label: M&A ({sub})")

    # --- Litigation / regulatory
    if re.search(r"litigation|dispute|action\(?s?\)? initiated|orders? passed|regulatory action|penalt|show[- ]cause|insolvency|nclt|arbitration", L):
        minor = re.search(r"(delay|late|non-?compliance|failure)[^.]{0,70}(submission|filing|intimation|disclosure|regulation)", body, I)
        return R("litigation_regulatory", "compliance_fine" if minor else "order", 0.93,
                 "label: litigation/regulatory" + ("; late-filing style fine" if minor else ""))

    # --- Shareholder meetings
    if re.search(r"annual general meeting|\bagm\b|\begm\b|extra-?ordinary general|shareholders?'? meeting|postal ballot|book closure", L):
        return R("shareholder_meeting", "postal_ballot" if "postal" in L else "notice", 0.92, "label: shareholder meeting")

    # --- Business updates
    if re.search(r"capacity addition|capex|new plant|expansion", L):
        return R("business_update", "capex", 0.9, "label: capacity/capex")
    if re.search(r"award of order|receipt of order|order win|bagging|new order|letter of award", L):
        return R("business_update", "order_win", 0.9, "label: order")
    if re.search(r"press release|media release", L):
        sub = "order_win" if re.search(r"(bags?|secur|receiv|won|awarded)[^.]{0,60}order", body, I) else "press_release"
        return R("business_update", sub, 0.85, f"label: press release ({sub})")
    if re.search(r"agreements?|mou|memorandum|partnership|collaboration", L):
        return R("business_update", "agreement", 0.85, "label: agreement/MoU")
    return None


def _board_outcome(body: str) -> Classification:
    """'Outcome of Board Meeting' is a container. The body says what was decided."""
    b = body
    if re.search(r"(approved|considered and approved|took on record|approve[sd]?)[^.]{0,140}(un)?audited[^.]{0,100}results", b, I):
        return R("results", "outcome", 0.85, "board outcome approving financial results")
    if re.search(r"(declared|recommended|approved)[^.]{0,80}dividend", b, I):
        return R("corporate_action", "dividend", 0.8, "board outcome declaring dividend")
    if re.search(r"(approved|approves)[^.]{0,100}(rights issue|\bqip\b|preferential|non-convertible|\bncds?\b|fund ?raising|raising of funds|debentures)", b, I):
        return R("fund_raise", "issue", 0.78, "board outcome approving fundraise")
    if re.search(r"(approved|approves)[^.]{0,100}(acquisition|merger|amalgamation|scheme of arrangement|demerger)", b, I):
        return R("m_and_a", "deal", 0.78, "board outcome approving M&A")
    if re.search(r"(approved|approves)[^.]{0,60}buy-?back", b, I):
        return R("corporate_action", "buyback", 0.8, "board outcome approving buyback")
    if re.search(r"(resign|cessation|appointment of)[^.]{0,100}(chief|managing director|\bceo\b|\bcfo\b|director)", b, I):
        m = _mgmt(b, True, "")
        return R(m.category, m.subtype, 0.75, "board outcome: " + m.reason)
    return R("board_meeting", "outcome", 0.7, "board outcome with no specific decision recognised")


# ---------------------------------------------------------------- body-only fallback
BODY_RULES = [  # each pattern needs verb + object context, not just a keyword
    (r"(approved|considered and approved)[^.]{0,120}(un)?audited[^.]{0,80}results", "results", "outcome"),
    (r"(resign|cessation|step(ped|ping)? down|appointed|appointment of)[^.]{0,100}(chief (executive|financial|operating)|managing director|\bceo\b|\bcfo\b|whole[- ]time director|independent director|\bdirector\b)", "management_change", None),
    (r"(crisil|icra|care ratings|india ratings|brickwork|acuite)[^.]{0,120}(reaffirm|upgrad|downgrad|assign|rating)", "credit_rating", "__rating"),
    (r"(show[- ]cause notice|order (passed|issued) by|penalty of|insolvency (petition|proceedings)|search and seizure|adjudication order)", "litigation_regulatory", "order"),
    (r"(declared|recommended)[^.]{0,60}dividend", "corporate_action", "dividend"),
    (r"(invocation|creation|release) of pledge", "shareholding_change", "__pledge"),
    (r"(approved|approves)[^.]{0,80}(rights issue|\bqip\b|preferential|non-convertible debentures|\bncds?\b|fund ?raising)", "fund_raise", "issue"),
    (r"(acquisition|acquire|merger|amalgamation|scheme of arrangement|joint venture|slump sale)[^.]{0,100}\b(of|with|in)\b", "m_and_a", "deal"),
    (r"(bags?|secured|awarded|won|received)[^.]{0,60}order", "business_update", "order_win"),
]
GENERIC_LABEL = re.compile(r"^(updates?|general updates?|others?|disclosures?|announcements?|intimation|disclosure under regulation 30.*|regulation 30.*)$", I)


def _by_body(L: str, body: str) -> Classification:
    generic = bool(GENERIC_LABEL.match(L)) or not L
    for rx, cat, sub in BODY_RULES:
        if re.search(rx, body, I):
            if sub == "__rating":
                sub = _rating_sub(body)
            elif sub == "__pledge":
                sub = _pledge_sub(body)
            elif cat == "management_change":
                m = _mgmt(body, True, "")
                cat, sub = m.category, m.subtype
            return R(cat, sub, 0.7 if generic else 0.62, f"body pattern ({'generic' if generic else 'unrecognised'} label)")
    if generic:
        return R("other", None, 0.65, "generic label, nothing specific in text")
    return R("needs_review", None, 0.2, f"unrecognised label '{L[:60]}', no clear pattern")


def classify(desc: str, text: str = "") -> Classification:
    lab = clean_label(desc)
    L = lab.lower()
    body = (text or "").strip()
    r = _by_label(L, lab, body) or _by_body(L, body)
    if r.confidence < MIN_CONFIDENCE and r.category != "needs_review":
        r = Classification("needs_review", None, r.confidence, f"low confidence; best guess {r.category}/{r.subtype}: {r.reason}")
    return r
