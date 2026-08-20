"""Convert numbers to words using the Indian numbering system (lakh / crore)."""

_ONES = [
    "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
    "Sixteen", "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
    "Eighty", "Ninety",
]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (" " + _ONES[ones] if ones else "")


def _three_digits(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(_ONES[hundreds] + " Hundred")
    if rest:
        parts.append(_two_digits(rest))
    return " ".join(parts)


def number_to_words(number: int) -> str:
    """Return the Indian-system word representation of a non-negative integer."""
    if number == 0:
        return "Zero"

    crore, remainder = divmod(number, 10_000_000)
    lakh, remainder = divmod(remainder, 100_000)
    thousand, remainder = divmod(remainder, 1_000)
    hundreds = remainder

    parts = []
    if crore:
        parts.append(number_to_words(crore) + " Crore")
    if lakh:
        parts.append(_two_digits(lakh) + " Lakh")
    if thousand:
        parts.append(_two_digits(thousand) + " Thousand")
    if hundreds:
        parts.append(_three_digits(hundreds))
    return " ".join(parts)


def rupees_in_words(amount: float) -> str:
    """Format a rupee amount as words, e.g. 'Rupees Twenty Four Thousand ... Only'."""
    rounded = round(float(amount) + 1e-9, 2)
    rupees = int(rounded)
    paise = int(round((rounded - rupees) * 100))

    words = "Rupees " + number_to_words(rupees)
    if paise:
        words += " and " + number_to_words(paise) + " Paise"
    return words + " Only"
