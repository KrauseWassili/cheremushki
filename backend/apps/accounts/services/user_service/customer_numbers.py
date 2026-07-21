from apps.accounts.global_identifier import GlobalIdentifier

CUSTOMER_NUMBER_KEY = "customer_number"
CUSTOMER_NUMBER_START = 100001
CUSTOMER_NUMBER_PREFIX = "K39"


def allocate_customer_number() -> str:
    """Allocate the next customer number using GlobalIdentifier."""
    sequence = GlobalIdentifier.next(CUSTOMER_NUMBER_KEY, default=CUSTOMER_NUMBER_START)
    return f"{CUSTOMER_NUMBER_PREFIX}-{sequence}"
