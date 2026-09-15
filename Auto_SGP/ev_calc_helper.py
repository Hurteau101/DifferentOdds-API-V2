# from typing import Union
# from Utils.helpers import decimal_to_american, american_to_decimal
#
# def get_percentage(o):  # converts American Odds to Percentage % (<= 1)
#     """
#     Convert American (moneyline) odds to a decimal probability between 0 and 1.
#
#     Args:
#         o (int|float|str): American-style odds (e.g. -125, 150). Strings will be converted to float.
#
#     Returns:
#         float: Probability in the range (0, 1).
#
#     Raises:
#         ValueError: If the provided odds cannot be converted to float.
#
#     Examples:
#         >>> get_percentage(-125)
#         0.5555555555555556
#     """
#     over_odds = float(o)
#     if over_odds <= 0:
#         over_percent = abs(over_odds) / (abs(over_odds) + 100)
#     else:
#         over_percent = 100 / (abs(over_odds) + 100)
#     return over_percent
#
#
# def get_odds(per):  # returns American Odds from Percentage % (<= 1)
#     """
#     Convert a decimal probability (0..1) to American (moneyline) odds.
#
#     Args:
#         per (float|int|str): Decimal probability (0..1). Strings will be converted to float.
#
#     Returns:
#         float: American odds (negative for favorites, positive for underdogs).
#
#     Examples:
#         >>> get_odds(0.6)
#         -150.0
#     """
#     nvig_per = float(per)
#     nvig_am = abs((100 * nvig_per) / (1 - nvig_per))
#     if nvig_am < 100:
#         nvig_am = abs((100 * (1 - nvig_per)) / nvig_per)
#     if nvig_per > 0.5:
#         nvig_am *= -1
#     return nvig_am
#
#
# def get_ev(am_odds: float, nvig_per: float) -> float:  # Gets Raw EV from American Odd and Nvig Percentage:
#     """
#     Calculate expected value (EV) as a percentage from American odds and a fair probability.
#
#     Args:
#         am_odds (float): American odds for the bet (e.g. -125, 150).
#         nvig_per (float): Decimal probability (0..1) representing the fair chance.
#
#     Returns:
#         float: Expected value expressed in percentage points (e.g. 5.0 for 5%).
#
#     Notes:
#         The function computes the expected return on a $1 stake and multiplies by 100 to
#         return percentage points.
#     """
#     n = float(nvig_per)
#     true_over_p = n
#     true_under_p = 1 - n
#     over_ml = float(am_odds)
#     if over_ml > 0:
#         true_over_ev = (1 * (abs(over_ml) / 100) * (true_over_p) - (1 * true_under_p))
#     else:
#         true_over_ev = (1 / (abs(over_ml) / 100) * (true_over_p) - (1 * true_under_p))
#
#     return true_over_ev * 100
#
#
# def get_ev_from_odds(odds: float, nvig: float) -> float:
#     """
#     Convenience wrapper to compute EV from American odds and an American-format NVIG.
#
#     Args:
#         odds (float): American odds for the bet.
#         nvig (float): American odds representing the fair (NVIG) price.
#
#     Returns:
#         float: EV expressed as percentage points.
#     """
#     return get_ev(odds, get_percentage(nvig))
#
#
# def linear_reduction(book_odds, is_percentage=False) -> float:
#     """Performs Linear Reduction on a list of American Odds.
#
#     Returns: Average Fair Odds after Linear Reduction.
#
#     If is_percentage is True, the input book_odds are treated as decimal probabilities (0..1)."""
#     weights = 0
#     weighted_odds = []
#     starting_weight = 1
#     book_odds = book_odds[:4]
#
#     for i in book_odds:
#         if is_percentage:
#             p = float(i)
#         else:
#             p = get_percentage(float(i))
#         weighted = p * starting_weight
#         weighted_odds.append(weighted)
#         weights += starting_weight
#         starting_weight -= 0.2
#         if starting_weight < 0.1:
#             starting_weight = 0.1
#
#     fair_percentage = sum(weighted_odds) / weights
#     fair_odds = get_odds(fair_percentage)
#     return fair_odds
#
#
# def tiered_fair_value(list, is_percentage=False):
#     """Calculates Tiered Fair Value using only the 2nd and 3rd best odds from a list."""
#     second = float(list[1])
#     third = float(list[2])
#
#     if is_percentage:
#         return get_odds((second + third) / 2)
#     else:
#         second_p = get_percentage(second)
#         third_p = get_percentage(third)
#         return get_odds((second_p + third_p) / 2)
#
#
# def get_sgp_data(normal_books: dict, sgp_results: dict, fair_odds: Union[dict | list]) -> dict:
#     """
#     Compute SGP (same-game parlay) adjustment coefficients and an adjusted fair odds value.
#
#     The function compares the implied parlay probability from single-leg (`normal_books`) prices
#     with the actual SGP parlay prices (`sgp_results`) for the same bookmakers. It calculates per-book
#     coefficients (sgp_parlay / normal_parlay) and uses the average coefficient to scale a provided
#     `fair_odds` into an `adjusted_fair_odds` that accounts for SGP correlation.
#
#     Args:
#         normal_books (dict): Mapping of bookmaker name -> list of American odds (single-leg odds).
#         sgp_results (dict): Mapping of bookmaker name -> American SGP parlay odds.
#         fair_odds (any dict | list): List of American Odds.
#
#     Returns:
#         dict: A summary dictionary with the following keys:
#             - 'adjusted_fair_odds' (float): adjusted American odds.
#             - 'average_coefficient' (float): average multiplier derived from SGP vs. normal parlay.
#             - 'book_data' (dict): per-book breakdown mapping bookmaker name -> {'odds': <sgp_odds>, 'ev': <ev>}.
#
#     Notes:
#         - Bookmaker name matching is normalized by lowercasing and removing spaces.
#         - The function computes per-book EVs and includes them under the returned 'book_data' key.
#     """
#
#     parlay_pricings = {}
#
#     for book_name, book_odds in normal_books.items():
#         parlay_odds = 1
#         for odds in book_odds:
#             parlay_odds *= get_percentage(float(odds))
#         parlay_pricings[book_name.lower().replace(" ", "")] = parlay_odds  # this is in probability form
#
#     coefficients = []
#
#     for book_name, sgp_odds in sgp_results.items():
#         absolute_name = book_name.lower().replace(" ", "")
#         if absolute_name in parlay_pricings:
#             normal_parlay_odds = parlay_pricings[absolute_name]  # probability form
#             sgp_parlay_odds = get_percentage(float(sgp_odds))  # probability form
#             coefficient = sgp_parlay_odds / normal_parlay_odds
#             coefficients.append(coefficient)
#
#     average_coefficient = sum(coefficients) / len(coefficients) if coefficients else 1
#
#     total_fair = 1
#     if type(fair_odds) is dict:
#         fair_odds = list(fair_odds.values())
#     for _fv in fair_odds:
#         total_fair *= get_percentage(_fv)
#     fair_odds_percentage = total_fair
#     adjusted_fair_odds_percentage = fair_odds_percentage * average_coefficient
#
#     returned_data = {}
#     returned_data['adjusted_fair_odds'] = get_odds(adjusted_fair_odds_percentage)
#     returned_data['average_coefficient'] = average_coefficient
#
#     book_data = {}
#     for book_name, sgp_odds in sgp_results.items():
#         sgp_ev = get_ev(float(sgp_odds), adjusted_fair_odds_percentage)
#         book_data[book_name] = {
#             'odds': sgp_odds,
#             'ev': sgp_ev
#         }
#
#     book_data = dict(sorted(book_data.items(), key=lambda x: x[1]['ev'], reverse=True))
#     weighted_fair_value = linear_reduction([float(v['odds']) for v in book_data.values()])
#     weighted_fair_percentage = get_percentage(weighted_fair_value)
#     weighted_book_data = {}
#     for book_name, sgp_odds in sgp_results.items():
#         new_ev = get_ev(float(sgp_odds), weighted_fair_percentage)
#         weighted_book_data[book_name] = {
#             'odds': sgp_odds,
#             'ev': new_ev
#         }
#
#     returned_data['book_data'] = book_data
#     returned_data['weighted_fair_value'] = weighted_fair_value
#     returned_data['weighted_book_data'] = weighted_book_data
#     return returned_data
#
#
# def parlay_odds(*odds_list):
#     """Calculate parlay odds from multiple American odds."""
#     parlay_decimal = 1.0
#     for odds in odds_list:
#         parlay_decimal *= american_to_decimal(odds)
#     return round(decimal_to_american(parlay_decimal), 0)




"""EV helpers for Auto SGP.

parlay_fair.py from the spec is pasted below, verbatim, between the LIFT TRANSFER markers.
Nothing in that block has been edited. get_sgp_data is the only adapter: it builds the
inputs those functions want out of the arguments it already receives, and maps their output
back onto the exact keys this module has always returned, so runner.py does not change.
"""

from typing import Union

from Utils.helpers import decimal_to_american, american_to_decimal


def get_percentage(o):  # converts American Odds to Percentage % (<= 1)
    """
    Convert American (moneyline) odds to a decimal probability between 0 and 1.

    Args:
        o (int|float|str): American-style odds (e.g. -125, 150). Strings will be converted to float.

    Returns:
        float: Probability in the range (0, 1).

    Raises:
        ValueError: If the provided odds cannot be converted to float.

    Examples:
        >>> get_percentage(-125)
        0.5555555555555556
    """
    over_odds = float(o)
    if over_odds <= 0:
        over_percent = abs(over_odds) / (abs(over_odds) + 100)
    else:
        over_percent = 100 / (abs(over_odds) + 100)
    return over_percent


def get_odds(per):  # returns American Odds from Percentage % (<= 1)
    """
    Convert a decimal probability (0..1) to American (moneyline) odds.

    Args:
        per (float|int|str): Decimal probability (0..1). Strings will be converted to float.

    Returns:
        float: American odds (negative for favorites, positive for underdogs).

    Examples:
        >>> get_odds(0.6)
        -150.0
    """
    nvig_per = float(per)
    nvig_am = abs((100 * nvig_per) / (1 - nvig_per))
    if nvig_am < 100:
        nvig_am = abs((100 * (1 - nvig_per)) / nvig_per)
    if nvig_per > 0.5:
        nvig_am *= -1
    return nvig_am


def get_ev(am_odds: float, nvig_per: float) -> float:  # Gets Raw EV from American Odd and Nvig Percentage:
    """
    Calculate expected value (EV) as a percentage from American odds and a fair probability.

    Args:
        am_odds (float): American odds for the bet (e.g. -125, 150).
        nvig_per (float): Decimal probability (0..1) representing the fair chance.

    Returns:
        float: Expected value expressed in percentage points (e.g. 5.0 for 5%).

    Notes:
        The function computes the expected return on a $1 stake and multiplies by 100 to
        return percentage points.
    """
    n = float(nvig_per)
    true_over_p = n
    true_under_p = 1 - n
    over_ml = float(am_odds)
    if over_ml > 0:
        true_over_ev = (1 * (abs(over_ml) / 100) * (true_over_p) - (1 * true_under_p))
    else:
        true_over_ev = (1 / (abs(over_ml) / 100) * (true_over_p) - (1 * true_under_p))

    return true_over_ev * 100


def get_ev_from_odds(odds: float, nvig: float) -> float:
    """
    Convenience wrapper to compute EV from American odds and an American-format NVIG.

    Args:
        odds (float): American odds for the bet.
        nvig (float): American odds representing the fair (NVIG) price.

    Returns:
        float: EV expressed as percentage points.
    """
    return get_ev(odds, get_percentage(nvig))


def linear_reduction(book_odds, is_percentage=False) -> float:
    """Performs Linear Reduction on a list of American Odds.

    Returns: Average Fair Odds after Linear Reduction.

    If is_percentage is True, the input book_odds are treated as decimal probabilities (0..1).

    Only valid for a single two-way market. Do not run it over parlay prices: averaging other
    books' parlay prices does not remove a book's own parlay vig."""
    weights = 0
    weighted_odds = []
    starting_weight = 1
    book_odds = book_odds[:4]

    for i in book_odds:
        if is_percentage:
            p = float(i)
        else:
            p = get_percentage(float(i))
        weighted = p * starting_weight
        weighted_odds.append(weighted)
        weights += starting_weight
        starting_weight -= 0.2
        if starting_weight < 0.1:
            starting_weight = 0.1

    fair_percentage = sum(weighted_odds) / weights
    fair_odds = get_odds(fair_percentage)
    return fair_odds


def tiered_fair_value(odds_list, is_percentage=False):
    """Calculates Tiered Fair Value using only the 2nd and 3rd best odds from a list."""
    second = float(odds_list[1])
    third = float(odds_list[2])

    if is_percentage:
        return get_odds((second + third) / 2)
    else:
        second_p = get_percentage(second)
        third_p = get_percentage(third)
        return get_odds((second_p + third_p) / 2)


# =====================================================================================
# LIFT TRANSFER - parlay_fair.py, verbatim. Do not edit anything below this marker
# except by replacing it with a new version of that file.
# =====================================================================================

"""Fair value and worst-case fair value for any same-game parlay, read off live prices.

Pipeline per combo:
  1. leg fairs     two-way legs: the de-vigged price. One-way legs (anytime, first, last):
                   de-vig the whole family against the event's two-sided total line.
  2. book lifts    each book's parlay price over the product of its own legs, with its
                   per-leg stacking charge (its own leg margin) taken out.
  3. fair / worst  legs x median lift, and cautious legs x lowest lift, inside the bounds
                   any joint probability must respect.
  4. price         EV is credited at no more than 1.10x the next-best book's payout.
  5. tier          best bet / +EV / show the boost needed to break even.
No fitted constants beyond the two guards in CAPS, no history, no stored state.
"""
import math
from statistics import median

PAYOUT_CAP_OVER_NEXT = 1.10   # one book far off the pack is stale or promotional
MAX_LABELLED_LEGS = 3         # every method overstates 4+ leg parlays; label nothing there
DEEP_LISTING = 0.6            # a book must price this share of a one-way family to be de-vigged
ONEWAY_MAX_OVERROUND = 1.5    # above this the listing holds people who will not play (voided bets)


# ---------------------------------------------------------------- prices

def implied(american):
    a = float(american)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def decimal(american):
    a = float(american)
    return 1 + (a / 100 if a > 0 else 100 / -a)


def to_american(p):
    return round(100 * (1 - p) / p, 2) if p <= 0.5 else round(-100 * p / (1 - p), 2)


# ---------------------------------------------------------------- 1. one-way legs

def total_line_rate(line, fair_over):
    """Poisson mean of the counted event (touchdowns, goals, cards) implied by a de-vigged
    two-sided total: the rate at which P(count > line) equals fair_over."""
    k = math.floor(float(line))
    lo, hi = 1e-6, 50.0
    for _ in range(80):
        rate = (lo + hi) / 2
        p_over = 1 - sum(math.exp(-rate) * rate ** i / math.factorial(i) for i in range(k + 1))
        lo, hi = (rate, hi) if p_over < fair_over else (lo, rate)
    return rate


def event_rate(total_lines):
    """total_lines: [(line, fair_over)] for one event's two-sided total IN THE FAMILY'S OWN PERIOD
    (a first-quarter scorer family needs a first-quarter total). Uses the half-point line priced
    closest to even. Rates add across periods: second half = full game - first half. With no
    total for the period the family cannot be rated."""
    usable = [(l, f) for l, f in total_lines if float(l) % 1 and 0 < f < 1]
    line, fair_over = min(usable, key=lambda t: abs(t[1] - 0.5))
    return total_line_rate(line, fair_over)


def oneway_fairs(book_quotes, rate, exclusive=False, none_listed=False):
    """
    book_quotes: {book: {outcome: american}} for ONE one-way family in ONE event
    rate:        event_rate() of the count the family pays on
    exclusive:   True for first/last-type families (one outcome wins), False for anytime-type
    none_listed: True when the family lists a "no scorer" outcome
    returns      {outcome: (fair, worst)} = median and lowest de-vigged probability over books,
                 or {} when the family cannot be rated: no deep listing, or books' prices sit more
                 than ONEWAY_MAX_OVERROUND above the de-vigged prices, which means the listing
                 includes participants whose bets are voided (soccer squads before lineups)

    Anytime: each outcome's implied rate mu = -ln(1 - q) is scaled so the family's rates add up
    to the event's expected count; fair = 1 - exp(-scaled mu). Exclusive: probabilities are
    scaled to sum to 1, or to 1 - P(no event) when no "no scorer" outcome is listed.
    A de-vigged price never sits above the book's own price (a short listing is not generosity).
    """
    n_outcomes = len({o for quotes in book_quotes.values() for o in quotes})
    per_outcome, overrounds = {}, []
    for book, quotes in book_quotes.items():
        if len(quotes) < DEEP_LISTING * n_outcomes:
            continue
        q = {o: implied(a) for o, a in quotes.items()}
        if exclusive:
            target = 1.0 if none_listed else 1 - math.exp(-rate)
            scale = target / sum(q.values())
            fairs = {o: p * scale for o, p in q.items()}
        else:
            mu = {o: -math.log(1 - min(p, 0.999)) for o, p in q.items()}
            c = rate / sum(mu.values())
            fairs = {o: 1 - math.exp(-c * m) for o, m in mu.items()}
        overrounds.append(sum(q.values()) / sum(fairs.values()))
        for o, f in fairs.items():
            per_outcome.setdefault(o, []).append(min(f, q[o]))
    if not overrounds or median(overrounds) > ONEWAY_MAX_OVERROUND:
        return {}
    return {o: (median(v), min(v)) for o, v in per_outcome.items()}


# ---------------------------------------------------------------- 2-3. parlay fair

def book_lift(leg_fairs, sgp_price, leg_prices):
    """One book's view of the correlation, its stacking charge removed; None if it misses a leg."""
    n = len(leg_fairs)
    if sgp_price is None or len(leg_prices) != n or any(x is None for x in leg_prices):
        return None
    lift = implied(sgp_price) / math.prod(implied(x) for x in leg_prices)
    leg_margin = math.exp(sum(math.log(implied(x) / p) for x, p in zip(leg_prices, leg_fairs)) / n)
    return lift / leg_margin ** (n - 1)


def _bounded(legs, lift):
    raw = math.prod(legs) * lift
    upper = min(legs)                          # never likelier than its least likely leg
    lower = max(0.0, sum(legs) - (len(legs) - 1))  # never less than the legs' forced overlap
    return min(max(raw, lower), upper), not lower <= raw <= upper


def sgp_fair(leg_fairs, quotes, leg_worst=None):
    """
    leg_fairs: fair probability of each leg (two-way: the de-vigged price; one-way: oneway_fairs fair)
    leg_worst: cautious probability of each leg (one-way: oneway_fairs worst); defaults to leg_fairs
    quotes:    {book: (sgp_american, [leg_american, ...])} with legs in the same order
    returns    dict(prob, worst, american, worst_american, lift, books, spread, clamped) or None
    """
    leg_worst = leg_worst or leg_fairs
    lifts = sorted(l for sgp, legs in quotes.values() if (l := book_lift(leg_fairs, sgp, legs)))
    if not lifts:
        return None
    mid, low = median(lifts), lifts[0]
    if len(lifts) == 1:                        # one book's view: halfway to independence
        mid = low = math.sqrt(mid)
    prob, clamped = _bounded(leg_fairs, mid)
    worst, _ = _bounded(leg_worst, low)
    worst = min(worst, prob)
    return dict(prob=prob, worst=worst, american=to_american(prob), worst_american=to_american(worst),
                lift=mid, books=len(lifts), spread=lifts[-1] / lifts[0], clamped=clamped)


# ---------------------------------------------------------------- 4-5. price and label

def credited_decimal(book, quotes):
    """The payout an edge is judged at: this book's, capped at PAYOUT_CAP_OVER_NEXT times the
    best payout among the other books quoting the parlay."""
    own = decimal(quotes[book][0])
    others = [decimal(p) for b, (p, _) in quotes.items() if b != book and p is not None]
    return min(own, PAYOUT_CAP_OVER_NEXT * max(others)) if others else own


def breakeven_boost(prob, american):
    """Smallest profit boost (0.25 = 25%) that makes this price worth taking; 0 if it already is."""
    profit = decimal(american) - 1
    return max(0.0, (1 / prob - 1) / profit - 1)


def rate_quote(fair, book, quotes, n_legs):
    """EV at the posted price, worst-case EV at the credited price, and the label to show."""
    price = quotes[book][0]
    ev = fair["prob"] * decimal(price) - 1
    worst_ev = fair["worst"] * credited_decimal(book, quotes) - 1
    if n_legs <= MAX_LABELLED_LEGS and fair["books"] >= 2 and worst_ev > 0:
        label = "best_bet"
    elif n_legs <= MAX_LABELLED_LEGS and ev > 0:
        label = "plus_ev"
    else:
        label = "boost"
    return dict(ev=ev, worst_ev=worst_ev, label=label, breakeven_boost=breakeven_boost(fair["prob"], price))

# =====================================================================================
# END parlay_fair.py
# =====================================================================================


def _build_quotes(normal_books: dict, sgp_results: dict, n_legs: int) -> dict:
    """{book: (sgp_american, [leg_american, ...])} for sgp_fair, keyed by the book name as it
    appears in sgp_results. Book names are matched lowercased and space-stripped, the same
    normalisation this module has always used."""
    by_name = {
        str(book).lower().replace(" ", ""): odds
        for book, odds in (normal_books or {}).items()
    }

    quotes = {}
    for book, sgp_odds in (sgp_results or {}).items():
        leg_prices = by_name.get(str(book).lower().replace(" ", ""))
        if sgp_odds is None or not leg_prices or len(leg_prices) != n_legs:
            continue
        quotes[book] = (sgp_odds, list(leg_prices))
    return quotes


def get_sgp_data(normal_books: dict, sgp_results: dict, fair_odds: Union[dict, list]) -> dict:
    """
    Compute the fair price of a same-game parlay and each book's EV against it.

    Adapter only: the pricing is sgp_fair() and rate_quote() from the block above. Each book's
    parlay price is divided by the product of its own leg prices and by its own per-leg
    stacking charge; the fair is the de-vigged legs times the median of what is left.

    Args:
        normal_books (dict): Mapping of bookmaker name -> list of American odds (single-leg odds).
        sgp_results (dict): Mapping of bookmaker name -> American SGP parlay odds.
        fair_odds (dict | list): Leg NVIGs as American odds, in leg order.

    Returns:
        dict: the same keys as before, so no consumer has to change.
            - 'weighted_fair_value' (float): fair parlay price, American odds. sgp_fair()['american'].
            - 'weighted_book_data' (dict): {book: {'odds': .., 'ev': ..}}, EV in percentage points,
              sorted by EV descending.
            - 'book_data' (dict): the same mapping.
            - 'adjusted_fair_odds' (float): the same fair price.
            - 'average_coefficient' (float): the median book lift, sgp_fair()['lift'].

    Notes:
        - rate_quote returns EV as a fraction; it is multiplied by 100 here because every 'ev'
          this module has ever returned is in percentage points, which is what discord_min_ev
          is compared against.
        - Leg order must match between fair_odds and each list in normal_books.
        - When no book priced both the parlay and all of its legs, sgp_fair returns None; the
          fair comes back None and the book dicts empty rather than carrying a made-up number.
    """
    if isinstance(fair_odds, dict):
        fair_odds = list(fair_odds.values())

    fair_odds = [o for o in (fair_odds or []) if o is not None]
    leg_fairs = [implied(o) for o in fair_odds]

    quotes = _build_quotes(normal_books, sgp_results, len(leg_fairs))
    fair = sgp_fair(leg_fairs, quotes) if leg_fairs and quotes else None

    if not fair:
        return {
            "adjusted_fair_odds": None,
            "average_coefficient": None,
            "book_data": {},
            "weighted_fair_value": None,
            "weighted_book_data": {},
        }

    book_data = {
        book: {
            "odds": quotes[book][0],
            "ev": rate_quote(fair, book, quotes, len(leg_fairs))["ev"] * 100,
        }
        for book in quotes
    }
    book_data = dict(sorted(book_data.items(), key=lambda x: x[1]["ev"], reverse=True))

    return {
        "adjusted_fair_odds": fair["american"],
        "average_coefficient": fair["lift"],
        "book_data": book_data,
        "weighted_fair_value": fair["american"],
        "weighted_book_data": book_data,
    }


def parlay_odds(*odds_list):
    """Calculate parlay odds from multiple American odds."""
    parlay_decimal = 1.0
    for odds in odds_list:
        parlay_decimal *= american_to_decimal(odds)
    return round(decimal_to_american(parlay_decimal), 0)