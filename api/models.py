from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from django.conf import settings

class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username must be set")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "ADMIN")  # 👈 Force Admin role

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(username, password, **extra_fields)
    



class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Student'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')

    objects = CustomUserManager()  # 👈 Use the custom manager

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def _str_(self):
        return f"{self.username} ({self.role})"

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    isbn = models.CharField(max_length=13)
    category = models.CharField(max_length=50)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = CloudinaryField('book image', blank=True, null=True)
    total_copies = models.PositiveIntegerField(default=1)       # default 1
    available_copies = models.PositiveIntegerField(default=1)   # default 1

    def _str_(self):
        return f"{self.title} by {self.author}"

# Individual physical copy of a book
class BookCopy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    accession_no = models.CharField(max_length=30, unique=True)  # Unique ID for each copy 

    def _str_(self):
        return f"{self.book.title} - Copy {self.accession_no}"
    

# Book request made by students
class BookRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'MEMBER'})
    book_copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE)
    request_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    admin_comment = models.TextField(blank=True, null=True)  # Optional note by admin

    def _str_(self):
        return f"{self.student.username} requested {self.book_copy.accession_no} ({self.status})"




# Top-level function for default return date
def default_return_date():
    return date.today() + timedelta(days=15)

CustomUser = get_user_model()

class BorrowRecord(models.Model):
    student = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'MEMBER'}
    )
    book_copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE)
    borrow_date = models.DateField(auto_now_add=True)
    return_date = models.DateField(default=default_return_date)  # Expected return date
    returned = models.BooleanField(default=False)
    fine = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)  # ✅ NEW

    FINE_PER_DAY = 5  # You can change the amount
    due_soon_notified = models.BooleanField(default=False)

    def calculate_fine(self):
        """Calculate and update fine based on overdue days."""
        if self.returned:
            return  # No fine if already returned

        today = date.today()
        overdue_days = (today - self.return_date).days

        if overdue_days > 0:
            self.fine = overdue_days * self.FINE_PER_DAY
            self.save()

    def _str_(self):
        return f"{self.student.username} borrowed {self.book_copy.accession_no}"





class BookNotificationRequest(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'MEMBER'})
    book = models.ForeignKey("Book", on_delete=models.CASCADE)
    notified = models.BooleanField(default=False)  # Has student been notified?

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "book")  # Avoid duplicate requests

    def _str_(self):
        return f"{self.student.username} wants {self.book.title}"


class Notification(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'MEMBER'})
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return f"Notification for {self.student.username}: {self.message[:20]}"


class EBook(models.Model):
    FORMAT_CHOICES = (
        ('PDF', 'PDF'),
        ('EPUB', 'EPUB'),
    )

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    isbn = models.CharField(max_length=13, blank=True, null=True)
    category = models.CharField(max_length=50)

    description = models.TextField(blank=True, null=True)

    # Cloudinary raw file upload (PDF / EPUB)
    ebook_file = CloudinaryField(
        resource_type='raw',
        folder='ebooks'
    )

    # Cloudinary image upload
    cover_image = CloudinaryField(
        'ebook cover',
        folder='ebook_covers',
        blank=True,
        null=True
    )

    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.format})"

class EBookBookmark(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'MEMBER'}
    )
    ebook = models.ForeignKey(EBook, on_delete=models.CASCADE)

    # For PDF: page_number
    page_number = models.PositiveIntegerField(null=True, blank=True)

    # For EPUB / advanced readers
    location = models.CharField(max_length=255, blank=True, null=True)

    note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "ebook", "page_number")

    def __str__(self):
        return f"{self.student.username} bookmark @ {self.page_number}"



class LibraryEntryRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'MEMBER'}
    )

    request_date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    admin_comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.student.username} - {self.status}"
    


class LibraryAttendance(models.Model):
    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'MEMBER'}
    )

    date = models.DateField(auto_now_add=True)
    check_in_time = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=(
            ('PRESENT', 'Present'),
            ('ABSENT', 'Absent'),
        ),
        default='ABSENT'
    )

    class Meta:
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student.username} - {self.date} ({self.status})"