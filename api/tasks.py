# tasks.py
from background_task import background
from datetime import date,timedelta
from .models import BorrowRecord, BookNotificationRequest, Notification, Book

@background(schedule=60)  # runs every minute
def update_fines_task():
    """
    Calculate fines for all unreturned books and notify students if they have fines.
    """
    records = BorrowRecord.objects.filter(returned=False)
    for record in records:
        previous_fine = record.fine
        record.calculate_fine()
        # Only notify if fine increased
        if record.fine > 0 and record.fine != previous_fine:
            Notification.objects.create(
                student=record.student,
                message=f"Your borrowed book '{record.book_copy.book.title}' is overdue. "
                        f"Current fine: ₹{record.fine:.2f}"
            )


def send_book_available_notifications():
    """
    Notify students when a requested book becomes available.
    """
    books_available = Book.objects.filter(available_copies__gt=0)

    for book in books_available:
        requests = BookNotificationRequest.objects.filter(book=book, notified=False)
        for req in requests:
            # Create notification
            Notification.objects.create(
                student=req.student,
                message=f"The book '{book.title}' is now available."
            )
            req.notified = True
            req.save()

@background(schedule=60)  # 60 seconds later for first run
def send_book_available_notifications_task():
    send_book_available_notifications()



@background(schedule=60)  # runs every minute
def due_date_reminder_task():
    """
    Notify students when their borrowed book is near the return date.
    """
    today = date.today()
    reminder_date = today + timedelta(days=2)  # 2 days before due

    records = BorrowRecord.objects.filter(
        returned=False,
        return_date=reminder_date,
        due_soon_notified=False
    )

    for record in records:
        Notification.objects.create(
            student=record.student,
            message=(
                f"Reminder: Your borrowed book "
                f"'{record.book_copy.book.title}' "
                f"is due on {record.return_date}. "
                f"Please return it on time to avoid fines."
            )
        )

        record.due_soon_notified = True
        record.save()