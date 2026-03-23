from datetime import date
from .models import BorrowRecord
from datetime import timedelta,timezone
from django.db.models import Count

def calculate_reading_streak(student):
    records = BorrowRecord.objects.filter(
        student=student
    ).order_by("-borrow_date")

    months = set()

    for r in records:
        months.add((r.borrow_date.year, r.borrow_date.month))

    months = sorted(months, reverse=True)

    streak = 0
    current = date.today()

    year = current.year
    month = current.month

    for y, m in months:
        if y == year and m == month:
            streak += 1

            month -= 1
            if month == 0:
                month = 12
                year -= 1
        else:
            break

    return streak


def get_badge(streak):

    if streak >= 6:
        return "Library Master"
    elif streak >= 3:
        return "Knowledge Seeker"
    elif streak >= 1:
        return "Beginner Reader"
    else:
        return "No Badge"
    



def get_trending_books():

    last_week = timezone.now() - timedelta(days=7)

    trending = (
        BorrowRecord.objects
        .filter(borrow_date__gte=last_week)
        .values(
            "book_copy__book__id",
            "book_copy__book__title",
            "book_copy__book__author",
            "book_copy__book__image"
        )
        .annotate(total_borrows=Count("id"))
        .order_by("-total_borrows")[:10]
    )

    return trending