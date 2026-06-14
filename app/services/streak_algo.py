from datetime import datetime, timedelta, timezone
from typing import Set
import zoneinfo

def calculate_streak(completed_dates: Set[str], current_date_str: str) -> int:
    """
    Calculates current streak based on a set of YYYY-MM-DD date strings.
    Implements lenient start: if current_date is not completed, starts checking from yesterday.
    """
    if not completed_dates:
        return 0
        
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
    streak = 0
    
    # Lenient start rule
    if current_date_str in completed_dates:
        check_date = current_date
    else:
        check_date = current_date - timedelta(days=1)
        
    while True:
        check_str = check_date.strftime("%Y-%m-%d")
        if check_str in completed_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
            
    return streak

def is_at_risk(completed_dates: Set[str], current_date_str: str, current_hour: int) -> bool:
    """
    Returns True if user completed yesterday but NOT today, and it's 6 PM (18:00) or later.
    """
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
    yesterday_str = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    
    completed_yesterday = yesterday_str in completed_dates
    completed_today = current_date_str in completed_dates
    
    if completed_yesterday and not completed_today and current_hour >= 18:
        return True
    return False

def get_local_now(timezone_str: str) -> datetime:
    """Returns a timezone-aware datetime object for the given timezone string."""
    if timezone_str.upper() == "UTC":
        return datetime.now(timezone.utc)
        
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
        return datetime.now(tz)
    except Exception:
        # Fallback natively to UTC if the timezone is invalid or Windows lacks tzdata
        return datetime.now(timezone.utc)
