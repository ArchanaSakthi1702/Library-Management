from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from datetime import date, timedelta

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

    def __str__(self):
        return f"{self.username} ({self.role})"

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    isbn = models.CharField(max_length=13)
    category = models.CharField(max_length=50)
    publisher = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="book_images/", blank=True, null=True)
    total_copies = models.PositiveIntegerField(default=1)       # default 1
    available_copies = models.PositiveIntegerField(default=1)   # default 1

    def __str__(self):
        return f"{self.title} by {self.author}"

# Individual physical copy of a book
class BookCopy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    accession_no = models.CharField(max_length=30, unique=True)  # Unique ID for each copy 

    def __str__(self):
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

    def __str__(self):
        return f"{self.student.username} requested {self.book_copy.accession_no} ({self.status})"




# Top-level function for default return date
def default_return_date():
    return date.today() + timedelta(days=15)

# Borrow record (only after admin approves)
class BorrowRecord(models.Model):
    student = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'MEMBER'}
    )
    book_copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE)
    borrow_date = models.DateField(auto_now_add=True)
    return_date = models.DateField(default=default_return_date)  # use function instead of lambda
    returned = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.username} borrowed {self.book_copy.accession_no}"