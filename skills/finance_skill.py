"""Everyday money math by voice — discount, GST, tip, EMI, interest.

100% local arithmetic (core/finance_math). quick_calc handles bare
"X% of Y"; these cover the framed real-life forms.
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="discount_calc",
    description="Work out a discount and final price (offline).",
    patterns=[
        "1500 pe 20 percent discount", "20 percent off on 1500",
        "discount calculate karo", "kitna discount milega",
        "2000 pe 30% off kitna", "sale price kya hogi",
        "500 pe 10 percent kam",
    ],
    required_entities=[],
)
def discount_calc(slots: dict) -> str:
    from core.finance_math import discount
    out = discount(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Amount aur discount % dono bolo — jaise '1500 pe 20% "
                   "off kitna'.")


@skill(
    name="gst_calc",
    description="Add GST/tax to an amount (offline).",
    patterns=[
        "150 ka 18 percent gst", "1000 pe 18% gst add karo",
        "gst nikalo", "gst laga ke total kitna", "tax add karo",
        "5000 pe 12 percent gst kitna", "18% gst on 2000",
    ],
    required_entities=[],
)
def gst_calc(slots: dict) -> str:
    from core.finance_math import add_percent
    text = slots.get("raw_text") or slots.get("text") or ""
    label = "Tax" if "tax" in text.lower() and "gst" not in text.lower() else "GST"
    out = add_percent(text, label=label)
    return out or ("Amount aur GST % bolo — jaise '2000 pe 18% gst kitna'.")


@skill(
    name="tip_calc",
    description="Calculate a restaurant tip and total bill (offline).",
    patterns=[
        "800 pe 10 percent tip", "tip calculate karo", "kitni tip doon",
        "1200 pe 15% tip kitni", "bill pe tip nikalo",
        "restaurant tip kitni hogi",
    ],
    required_entities=[],
)
def tip_calc(slots: dict) -> str:
    from core.finance_math import tip
    out = tip(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Bill amount aur tip % bolo — jaise '800 pe 10% tip'.")


@skill(
    name="emi_calc",
    description="Loan EMI (monthly instalment) calculator (offline).",
    patterns=[
        "500000 ka loan 12 percent pe 24 months emi", "emi calculate karo",
        "loan emi kitni hogi", "500000 loan 10% 5 saal emi",
        "car loan emi nikalo", "home loan emi kitni",
        "monthly instalment kitna hoga",
    ],
    required_entities=[],
)
def emi_calc(slots: dict) -> str:
    from core.finance_math import emi
    out = emi(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Loan amount, rate % aur months/saal bolo — jaise "
                   "'500000 loan 12% 24 months emi'.")


@skill(
    name="simple_interest",
    description="Simple interest on a principal (offline).",
    patterns=[
        "10000 pe 8 percent 3 saal interest", "simple interest nikalo",
        "interest kitna lagega", "20000 pe 6% 2 saal ka interest",
        "byaj kitna hoga", "interest calculate karo",
    ],
    required_entities=[],
)
def simple_interest(slots: dict) -> str:
    from core.finance_math import simple_interest as _si
    out = _si(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Principal, rate % aur saal bolo — jaise '10000 pe 8% "
                   "3 saal interest'.")


@skill(
    name="compound_interest",
    description="Compound interest & maturity value with compounding frequency (offline).",
    patterns=[
        "compound interest nikalo", "100000 pe 8% 5 saal compound",
        "chakravriddhi byaj kitna hoga", "compound interest calculate karo",
        "quarterly compound interest batao", "maturity value nikalo",
        "50000 pe 10% 2 saal monthly compound",
    ],
    required_entities=[],
)
def compound_interest(slots: dict) -> str:
    from core.finance_math import compound_interest as _ci
    out = _ci(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Principal, rate % aur saal bolo (frequency optional) — "
                   "jaise '100000 pe 8% 5 saal quarterly compound'.")


@skill(
    name="profit_loss",
    description="Profit/loss amount and percentage from cost & selling price (offline).",
    patterns=[
        "kharida 100 becha 150 profit", "profit loss nikaalo",
        "cost 200 sold 150 kitna loss", "profit percentage batao",
        "kitna fayda hua", "kitna nuksan hua bech ke",
        "cost price selling price se profit",
    ],
    required_entities=[],
)
def profit_loss(slots: dict) -> str:
    from core.finance_math import profit_loss as _pl
    out = _pl(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Cost aur selling price dono bolo — jaise 'kharida 100 "
                   "becha 150'.")


@skill(
    name="discount_stack",
    description="Effective discount & final price for stacked/sequential discounts (offline).",
    patterns=[
        "1000 pe 20% phir 10% off kitna", "stacked discount nikaalo",
        "20% then 10% effective discount", "do discount milake kitna",
        "extra discount ke baad final price", "double discount kitna banega",
    ],
    required_entities=[],
)
def discount_stack(slots: dict) -> str:
    from core.finance_math import discount_stack as _ds
    return _ds(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="electricity_bill",
    description="Estimate an electricity bill from units (and rate if given) (offline).",
    patterns=[
        "350 units ka bill kitna", "electricity bill nikaalo",
        "300 units 8 rupee bill", "bijli ka bill kitna hoga",
        "units se bill batao", "light bill calculate karo",
    ],
    required_entities=[],
)
def electricity_bill(slots: dict) -> str:
    from core.finance_math import electricity_bill as _eb
    return _eb(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="overtime_pay",
    description="Overtime pay from hours, hourly rate and multiplier (offline).",
    patterns=[
        "8 hours 200 per hour overtime pay", "overtime pay nikaalo",
        "5 ghante extra kaam ka kitna milega", "overtime kitna banega",
        "double rate pe overtime", "extra hours ka payment batao",
    ],
    required_entities=[],
)
def overtime_pay(slots: dict) -> str:
    from core.finance_math import overtime_pay as _op
    return _op(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="sip_calculator",
    description="SIP maturity value from monthly investment, return % and years (offline).",
    patterns=[
        "5000 monthly 12% 10 saal sip maturity", "sip calculator",
        "monthly sip ka future value", "sip me kitna banega 15 saal me",
        "mutual fund sip return nikaalo", "sip maturity amount batao",
    ],
    required_entities=[],
)
def sip_calculator(slots: dict) -> str:
    from core.finance_math import sip_calculator as _sc
    out = _sc(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Monthly amount, return % aur saal bolo — jaise "
                   "'5000 monthly 12% 10 saal'.")


@skill(
    name="savings_goal",
    description="Monthly saving needed to reach a target amount in N years (offline).",
    patterns=[
        "5 lakh 2 saal me kitna monthly bachau", "savings goal calculate karo",
        "target amount ke liye monthly saving", "kitna bachana padega har mahine",
        "goal ke liye monthly kitna", "3 saal me 5 lakh chahiye monthly",
    ],
    required_entities=[],
)
def savings_goal(slots: dict) -> str:
    from core.finance_math import savings_goal as _sg
    return _sg(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="inflation_adjust",
    description="Future cost and today's-worth of money after years of inflation (offline).",
    patterns=[
        "1 lakh 10 saal baad kitne ke barabar", "inflation adjust karo",
        "mehngai ke hisaab se future value", "aaj ke paise 10 saal baad kitne",
        "6% inflation pe value kya hogi", "inflation ka asar batao",
    ],
    required_entities=[],
)
def inflation_adjust(slots: dict) -> str:
    from core.finance_math import inflation_adjust as _ia
    return _ia(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="rule_of_72",
    description="Rule of 72: years to double your money at a rate, or the rate needed (offline).",
    patterns=[
        "8% pe paisa kab double hoga", "rule of 72 batao",
        "kitne saal me paisa double", "5 saal me double kaunsa return chahiye",
        "money double hone me kitna time", "double karne ka rate kya ho",
    ],
    required_entities=[],
)
def rule_of_72(slots: dict) -> str:
    from core.finance_math import rule_of_72 as _r72
    return _r72(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="cagr",
    description="Compound annual growth rate between two values over years (offline).",
    patterns=[
        "1 lakh se 2 lakh 5 saal cagr", "cagr nikaalo",
        "investment ka annual growth rate", "kitne percent per year grow kiya",
        "50000 se 150000 3 saal cagr", "cagr calculate karo",
    ],
    required_entities=[],
)
def cagr(slots: dict) -> str:
    from core.finance_math import cagr as _cagr
    return _cagr(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="down_payment",
    description="Down-payment amount and loan needed from home price and down % (offline).",
    patterns=[
        "50 lakh ghar 20% down payment kitna", "down payment nikaalo",
        "kitna loan lena padega ghar pe", "home ka down payment aur loan",
        "20% down pe kitna loan", "down payment calculate karo",
    ],
    required_entities=[],
)
def down_payment(slots: dict) -> str:
    from core.finance_math import down_payment as _dp
    return _dp(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="break_even",
    description="Break-even units from fixed cost, price and per-unit cost (offline).",
    patterns=[
        "fixed 50000 price 200 variable cost 120 break even",
        "break even point nikaalo", "kitne units bechne padenge profit ke liye",
        "break even units batao", "no profit no loss kitne units pe",
        "break even calculate karo",
    ],
    required_entities=[],
)
def break_even(slots: dict) -> str:
    from core.finance_math import break_even as _be
    return _be(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="markup_margin",
    description="Selling price from cost + markup%, or cost + margin% (offline).",
    patterns=[
        "cost 100 markup 25% selling price", "markup margin nikaalo",
        "cost 100 margin 20% pe kitne me bechu", "selling price kya rakhu",
        "markup se selling price", "margin ke hisaab se price",
    ],
    required_entities=[],
)
def markup_margin(slots: dict) -> str:
    from core.finance_math import markup_margin as _mm
    return _mm(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="gst_inclusive",
    description="Extract base price + tax from a GST-inclusive total (reverse GST, offline).",
    patterns=[
        "1180 me se 18% gst nikaalo", "gst included amount se base nikaalo",
        "total me se gst alag karo", "reverse gst calculate karo",
        "price me kitna gst tha", "gst hataake base price batao",
    ],
    required_entities=[],
)
def gst_inclusive(slots: dict) -> str:
    from core.finance_math import gst_inclusive as _gi
    return _gi(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="appliance_power_cost",
    description="Electricity cost of an appliance from wattage, hours and rate (offline).",
    patterns=[
        "1500 watt 8 hours daily kitna bill", "appliance power cost nikaalo",
        "AC ka monthly bill kitna aayega", "watt se electricity cost",
        "geyser kitni bijli khaayega", "appliance units aur cost batao",
    ],
    required_entities=[],
)
def appliance_power_cost(slots: dict) -> str:
    from core.finance_math import appliance_power_cost as _ap
    return _ap(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="percent_change",
    description="Percentage increase/decrease between two values (offline).",
    patterns=[
        "100 se 150 kitna percent badha", "percentage change nikalo",
        "kitne percent ka izafa hua", "50 se 40 kitna percent gira",
        "200 se 250 percentage change", "kitni percent badhotri hui",
        "percent increase batao", "percent decrease kitna hai",
    ],
    required_entities=[],
)
def percent_change(slots: dict) -> str:
    from core.finance_math import percent_change as _pc
    out = _pc(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Do values do — 'A se B' — jaise '100 se 150 kitna "
                   "percent badha'.")
