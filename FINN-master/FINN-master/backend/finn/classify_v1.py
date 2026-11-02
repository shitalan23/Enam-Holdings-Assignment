"""Rule-based announcement classifier (Tier 0: no LLM, no cost, deterministic).

Follows the taxonomy in the ENAM reference document. A filing can match several
categories (an 'Outcome of Board Meeting' often covers results + dividend + an
appointment), so we collect every match, pick the primary by weight, and keep the
rest as secondary tags. Exclusion patterns stop the classic false positives
(auditor appointments, ESOP allotments, unclaimed-dividend transfers).

An LLM is only worth calling for filings that land in 'unclassified' with a long
body; that hook is left for P1 (`category_method` records which path decided).
"""
import re
from dataclasses import dataclass, field

# Base weight used only to pick a primary category when several match.
PICK_WEIGHT = {
    "results": 90, "M&A": 85, "litigation": 80, "management_change": 75,
    "fund_raise": 72, "credit_rating": 70, "pledging": 68, "bonus_split": 60,
    "capex": 58, "dividend": 55, "earnings_call": 45, "press_release": 35,
    "insider_trading": 32, "investor_meetings": 25, "agm_egm": 20,
    "postal_ballot": 18, "unclassified": 0,
}

I = re.IGNORECASE
# (category, include-regex, exclude-regex or None)
RULES = [
    ("credit_rating", r"credit rating|rating (action|assigned|reaffirm|upgrade|downgrad|revis)|\bcrisil\b|\bicra\b|care ratings|india ratings|\bind-?ra\b|brickwork|acuite|reaffirm", None),
    ("pledging", r"pledg|invocation of|encumbrance", None),
    ("insider_trading", r"insider trading|regulation 7\s?\((1|2)\)|trading by (promoter|designated|director)|sale/purchase of shares by", None),
    ("litigation", r"litigation|lawsuit|\bcourt\b|tribunal|\bnclt\b|\bnclat\b|show[- ]cause|penalt|fine of|sebi order|insolvency|winding[- ]up|search and seizure|demand (notice|order)|adjudicat|regulatory action|\bcbi\b|enforcement directorate", r"unclaimed"),
    ("management_change", r"appoint|resign|cessation|retire|re-?appointment|step(ping)? down|demise|change in (director|management|key managerial)|chief (executive|financial|operating|technology|risk)|\b(ceo|cfo|coo|cto|cro)\b|managing director|company secretary|compliance officer|whole[- ]time director|independent director|senior management",
        r"statutory auditor|secretarial auditor|internal auditor|cost auditor|scrutini[sz]er|registrar|share transfer agent|auditors?\b.*appoint|appoint.*\bauditors?\b|debenture trustee"),
    ("M&A", r"acquisition|acquire|merger|amalgamation|demerger|scheme of arrangement|joint venture|\bjv\b|subsidiary|stake (sale|purchase)|divest|slump sale|business transfer|takeover", r"regulation 29|regulation 31|sast|substantial acquisition of shares|takeover regulations"),
    ("fund_raise", r"rights issue|\bqip\b|qualified institutions? placement|preferential (issue|allotment)|buy-?back|commercial paper|non-convertible debenture|\bncd\b|fund ?raising|raising of funds|share warrants|private placement|allotment of (securities|equity|debentures|ncd)", r"esop|employee stock|stock option|esos|share based employee"),
    ("results", r"financial results|results for the (quarter|year|half)|quarterly results|unaudited|audited (financial|standalone|consolidated)|quarter ended|year ended|half year ended|results presentation|investor presentation", None),
    ("dividend", r"dividend|record date", r"unclaimed|unpaid|iepf|investor education"),
    ("bonus_split", r"bonus (issue|shares)|stock split|sub-?division of (equity )?shares|split of (equity )?shares", None),
    ("capex", r"capex|capital expenditure|new (plant|facility|factory|unit)|capacity (expansion|addition)|greenfield|brownfield|commissioning|expansion of (plant|manufacturing)|set up (a )?(new )?(plant|facility|manufacturing)", None),
    ("earnings_call", r"earnings call|conference call|\bconcall\b|transcript|audio recording|results call", None),
    ("investor_meetings", r"analysts?|institutional investor|investor meet|one[- ]on[- ]one|investor conference|group meeting|meeting update", None),
    ("postal_ballot", r"postal ballot|e-?voting", None),
    ("agm_egm", r"annual general meeting|extra-?ordinary general meeting|\bagm\b|\begm\b", None),
    ("press_release", r"press release|media release|order(s)? (win|received|bagged)|bags? order|letter of award|launch(es|ed)? |partnership|clarification (on|sought)|rumou?r|price movement", None),
]
COMPILED = [(c, re.compile(p, I), re.compile(x, I) if x else None) for c, p, x in RULES]

ROUTINE_HINTS = re.compile(
    r"trading window|compliance certificate|reg(ulation)? 74|reg(ulation)? 40|newspaper publication|"
    r"esg|business responsibility|loss of share certificate|duplicate share|certificate under|"
    r"disclosure under regulation 30|updates?$|shareholding pattern|related party transactions? (for|report)|"
    r"voting results of|scrutini[sz]er", I)

INTIMATION = re.compile(r"intimation|prior intimation|notice of|schedule of|will be held|to consider|scheduled", I)
OUTCOME = re.compile(r"outcome|has approved|considered and approved|were approved|board approved|approved the|submitted|enclosed|\bpublished\b", I)
EXIT = re.compile(r"resign|cessation|retire|step(ping)? down|demise|relinquish|ceases?", I)
TOP = re.compile(r"chief executive|chief financial|chief operating|managing director|\bceo\b|\bcfo\b|\bcoo\b|chairman|whole[- ]time director|chief (technology|risk|business)|\bcto\b|\bcro\b", I)
KMP = re.compile(r"company secretary|compliance officer|\bcs\b", I)


@dataclass
class Classification:
    category: str
    subtype: str | None = None
    secondary: list[str] = field(default_factory=list)
    method: str = "rules"


def _norm_desc(desc: str) -> str:
    # NSE's combined label "Analysts/Institutional Investor Meet/Con. Call Updates"
    # would match both calls and meetings; flatten it so the body text decides.
    return re.sub(r"meet/con\.?\s*call", "meeting", desc or "", flags=I)


def _subtype(category: str, blob: str) -> str | None:
    if category in ("results", "dividend", "fund_raise", "earnings_call", "agm_egm", "postal_ballot"):
        if OUTCOME.search(blob):
            return "outcome"
        if INTIMATION.search(blob):
            return "intimation"
        return "outcome" if category == "results" else None
    if category == "management_change":
        exit_ = bool(EXIT.search(blob))
        level = "top" if TOP.search(blob) else ("kmp" if KMP.search(blob) else "director")
        return f"{level}_{'exit' if exit_ else 'entry'}"
    if category == "credit_rating":
        if re.search(r"downgrad|revised downward|lowered|negative", blob, I):
            return "downgrade"
        if re.search(r"upgrad|revised upward|positive", blob, I):
            return "upgrade"
        if re.search(r"reaffirm", blob, I):
            return "reaffirm"
        return "assign"
    if category == "pledging":
        if re.search(r"invo(k|c)", blob, I):
            return "invoked"
        if re.search(r"releas|revok", blob, I):
            return "released"
        return "created"
    return None


def classify(desc: str, text: str = "") -> Classification:
    d = _norm_desc(desc)
    body = text or ""
    blob = f"{d}. {body}"
    scored: dict[str, int] = {}
    for cat, inc, exc in COMPILED:
        excluded = bool(exc and exc.search(blob))
        in_desc = bool(inc.search(d)) and not excluded
        in_body = bool(inc.search(body)) and not excluded
        if in_desc or in_body:
            scored[cat] = PICK_WEIGHT[cat] + (30 if in_desc else 0)
    if not scored:
        sub = "routine" if ROUTINE_HINTS.search(blob) else None
        return Classification("unclassified", sub)
    if "earnings_call" in scored and "investor_meetings" in scored:
        scored["earnings_call"] = scored["investor_meetings"] + 1  # more specific wins
    ranked = sorted(scored, key=scored.get, reverse=True)
    primary = ranked[0]
    return Classification(primary, _subtype(primary, blob), ranked[1:3])
