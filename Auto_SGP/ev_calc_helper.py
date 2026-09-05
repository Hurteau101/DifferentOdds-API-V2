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

    If is_percentage is True, the input book_odds are treated as decimal probabilities (0..1)."""
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


def tiered_fair_value(list, is_percentage=False):
    """Calculates Tiered Fair Value using only the 2nd and 3rd best odds from a list."""
    second = float(list[1])
    third = float(list[2])

    if is_percentage:
        return get_odds((second + third) / 2)
    else:
        second_p = get_percentage(second)
        third_p = get_percentage(third)
        return get_odds((second_p + third_p) / 2)


def get_sgp_data(normal_books: dict, sgp_results: dict, fair_odds: Union[dict | list]) -> dict:
    """
    Compute SGP (same-game parlay) adjustment coefficients and an adjusted fair odds value.

    The function compares the implied parlay probability from single-leg (`normal_books`) prices
    with the actual SGP parlay prices (`sgp_results`) for the same bookmakers. It calculates per-book
    coefficients (sgp_parlay / normal_parlay) and uses the average coefficient to scale a provided
    `fair_odds` into an `adjusted_fair_odds` that accounts for SGP correlation.

    Args:
        normal_books (dict): Mapping of bookmaker name -> list of American odds (single-leg odds).
        sgp_results (dict): Mapping of bookmaker name -> American SGP parlay odds.
        fair_odds (any dict | list): List of American Odds.

    Returns:
        dict: A summary dictionary with the following keys:
            - 'adjusted_fair_odds' (float): adjusted American odds.
            - 'average_coefficient' (float): average multiplier derived from SGP vs. normal parlay.
            - 'book_data' (dict): per-book breakdown mapping bookmaker name -> {'odds': <sgp_odds>, 'ev': <ev>}.

    Notes:
        - Bookmaker name matching is normalized by lowercasing and removing spaces.
        - The function computes per-book EVs and includes them under the returned 'book_data' key.
    """

    parlay_pricings = {}

    for book_name, book_odds in normal_books.items():
        parlay_odds = 1
        for odds in book_odds:
            parlay_odds *= get_percentage(float(odds))
        parlay_pricings[book_name.lower().replace(" ", "")] = parlay_odds  # this is in probability form

    coefficients = []

    for book_name, sgp_odds in sgp_results.items():
        absolute_name = book_name.lower().replace(" ", "")
        if absolute_name in parlay_pricings:
            normal_parlay_odds = parlay_pricings[absolute_name]  # probability form
            sgp_parlay_odds = get_percentage(float(sgp_odds))  # probability form
            coefficient = sgp_parlay_odds / normal_parlay_odds
            coefficients.append(coefficient)

    average_coefficient = sum(coefficients) / len(coefficients) if coefficients else 1

    total_fair = 1
    if type(fair_odds) is dict:
        fair_odds = list(fair_odds.values())
    for _fv in fair_odds:
        total_fair *= get_percentage(_fv)
    fair_odds_percentage = total_fair
    adjusted_fair_odds_percentage = fair_odds_percentage * average_coefficient

    returned_data = {}
    returned_data['adjusted_fair_odds'] = get_odds(adjusted_fair_odds_percentage)
    returned_data['average_coefficient'] = average_coefficient

    book_data = {}
    for book_name, sgp_odds in sgp_results.items():
        sgp_ev = get_ev(float(sgp_odds), adjusted_fair_odds_percentage)
        book_data[book_name] = {
            'odds': sgp_odds,
            'ev': sgp_ev
        }

    book_data = dict(sorted(book_data.items(), key=lambda x: x[1]['ev'], reverse=True))
    weighted_fair_value = linear_reduction([float(v['odds']) for v in book_data.values()])
    weighted_fair_percentage = get_percentage(weighted_fair_value)
    weighted_book_data = {}
    for book_name, sgp_odds in sgp_results.items():
        new_ev = get_ev(float(sgp_odds), weighted_fair_percentage)
        weighted_book_data[book_name] = {
            'odds': sgp_odds,
            'ev': new_ev
        }

    returned_data['book_data'] = book_data
    returned_data['weighted_fair_value'] = weighted_fair_value
    returned_data['weighted_book_data'] = weighted_book_data
    return returned_data


def parlay_odds(*odds_list):
    """Calculate parlay odds from multiple American odds."""
    parlay_decimal = 1.0
    for odds in odds_list:
        parlay_decimal *= american_to_decimal(odds)
    return round(decimal_to_american(parlay_decimal), 0)