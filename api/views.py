from rest_framework import generics,status,permissions
from .models import CustomUser,Book,BookCopy,BookRequest,BorrowRecord,BookNotificationRequest,Notification
from .serializers import UserRegisterSerializer,BookSerializer,BookRequestSerializer,BorrowRecordSerializer,UserSerializer,StudentBorrowRecordSerializer,BookNotificationRequestSerializer,NotificationSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from api import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView

class RequestBookNotification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        student = request.user
        try:
            book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            return Response({"detail": "Book not found"}, status=status.HTTP_404_NOT_FOUND)

        obj, created = BookNotificationRequest.objects.get_or_create(student=student, book=book)
        if not created:
            return Response({"detail": "You already requested notification for this book"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BookNotificationRequestSerializer(obj)
        return Response(serializer.data)


class RegisterUserView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserRegisterSerializer


class UserLoginView(APIView):
    def post(self, request):
        username = request.data.get("username")   # roll_no for students, username for admins
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful",
                "role": user.role,
                "username": user.username,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )




# Custom permission: only admins can add books
class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN"


class BookCreateView(generics.CreateAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAdminUser]

    def generate_accession_no(self):
        """Generate a unique accession number across all books"""
        total_copies = BookCopy.objects.count() + 1
        return f"ACC{total_copies:05d}"  # e.g., ACC00001, ACC00002 ...

    def create(self, request, *args, **kwargs):
        isbn = request.data.get("isbn")
        existing_book = Book.objects.filter(isbn=isbn).first()

        if existing_book:
            # If book already exists → just add ONE new copy
            accession_no = self.generate_accession_no()
            BookCopy.objects.create(book=existing_book, accession_no=accession_no)

            # Update book counts
            existing_book.total_copies += 1
            existing_book.available_copies += 1
            existing_book.save()

            serializer = self.get_serializer(existing_book)
            return Response(
                {
                    "message": "Existing book found. Added a new copy.",
                    "book": serializer.data,
                    "new_accession_no": accession_no,
                },
                status=status.HTTP_200_OK,
            )

        # New book → create it + user-defined copies
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        book = serializer.save()

        # Get requested copies (default 1 if not provided)
        total_copies = int(request.data.get("total_copies", 1))
        available_copies = int(request.data.get("available_copies", total_copies))

        # Create BookCopy objects for each copy
        accession_numbers = []
        for _ in range(total_copies):
            accession_no = self.generate_accession_no()
            accession_numbers.append(accession_no)
            BookCopy.objects.create(book=book, accession_no=accession_no)

        # Update counts
        book.total_copies = total_copies
        book.available_copies = available_copies
        book.save()

        return Response(
            {
                "message": f"New book created with {total_copies} copies.",
                "book": serializer.data,
                "accession_numbers": accession_numbers,
            },
            status=status.HTTP_201_CREATED,
        )


from django.db import transaction

# ---------------- Update book (PUT/PATCH)
class BookUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

    def generate_accession_no(self):
        while True:
            with transaction.atomic():
                # Lock the last BookCopy and Book rows to prevent race conditions
                last_copy = BookCopy.objects.select_for_update().order_by("-id").first()
                last_book = Book.objects.select_for_update().order_by("-id").first()
                
                last_num_copy = 0
                last_num_book = 0

                if last_copy and last_copy.accession_no.startswith("ACC"):
                    try:
                        last_num_copy = int(last_copy.accession_no.replace("ACC", ""))
                    except ValueError:
                        last_num_copy = BookCopy.objects.count()

                if last_book and hasattr(last_book, 'accession_no') and last_book.accession_no.startswith("ACC"):
                    try:
                        last_num_book = int(last_book.accession_no.replace("ACC", ""))
                    except ValueError:
                        last_num_book = Book.objects.count()

                # Take the max of both to avoid collisions
                next_num = max(last_num_copy, last_num_book) + 1
                accession_no = f"ACC{next_num:05d}"

                # Check uniqueness across both models
                exists_in_copy = BookCopy.objects.filter(accession_no=accession_no).exists()
                exists_in_book = Book.objects.filter(accession_no=accession_no).exists() if hasattr(Book, 'accession_no') else False

                if not exists_in_copy and not exists_in_book:
                    return accession_no

    def update(self, request, *args, **kwargs):
        book = self.get_object()
        old_total = book.total_copies

        serializer = self.get_serializer(book, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        book = serializer.save()

        new_total = book.total_copies

        # Case 1: total_copies increased → add new copies
        if new_total > old_total:
            copies_to_add = new_total - old_total
            for _ in range(copies_to_add):
                accession_no = self.generate_accession_no()
                BookCopy.objects.create(book=book, accession_no=accession_no)
                book.available_copies += 1
            book.save()

        # Case 2: total_copies decreased → block update
        elif new_total < old_total:
            return Response(
                {"warning": "You cannot decrease total copies. Only increasing is allowed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(serializer.data)
    

class BookUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

    def generate_accession_no(self):
        """Generate a guaranteed unique accession number"""
        last_copy = BookCopy.objects.order_by("-id").first()
        if last_copy and last_copy.accession_no.startswith("ACC"):
            try:
                last_num = int(last_copy.accession_no.replace("ACC", ""))
            except ValueError:
                last_num = BookCopy.objects.count()
            next_num = last_num + 1
        else:
            next_num = 1
        return f"ACC{next_num:05d}"

    def update(self, request, *args, **kwargs):
        book = self.get_object()
        old_total = book.total_copies
        old_available = book.available_copies

        serializer = self.get_serializer(book, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_total = serializer.validated_data.get("total_copies", old_total)

        # Block decreasing copies
        if new_total < old_total:
            return Response(
                {"warning": "You cannot decrease total copies. Only increasing is allowed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        book = serializer.save()

        # Add missing copies
        if new_total > old_total:
            copies_to_add = new_total - old_total
            new_copies = []
            for _ in range(copies_to_add):
                accession_no = self.generate_accession_no()
                new_copies.append(BookCopy(book=book, accession_no=accession_no))

            BookCopy.objects.bulk_create(new_copies)

            book.available_copies = old_available + copies_to_add
            book.save()

        return Response(self.get_serializer(book).data)


# ---------------- Delete single book
class BookDeleteView(generics.DestroyAPIView):
    queryset = Book.objects.all()
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

# ---------------- Bulk delete books
class BookBulkDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        """
        Accepts JSON array of book IDs to delete:
        { "ids": [1, 2, 5] }
        """
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"error": "No book IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        books = Book.objects.filter(id__in=ids)
        count = books.count()
        books.delete()  # This will also delete related BookCopy due to on_delete=models.CASCADE
        return Response({"message": f"{count} book(s) deleted successfully."}, status=status.HTTP_200_OK)
    



# -----------------------------
# Permission: Only Admin can approve/reject requests
# -----------------------------
class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN"


# -----------------------------
# Student: Request a book copy
# -----------------------------
class BookRequestCreateView(generics.CreateAPIView):
    queryset = BookRequest.objects.all()
    serializer_class = BookRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        book_copy = serializer.validated_data['book_copy']

        # Check if the copy is already borrowed
        if BorrowRecord.objects.filter(book_copy=book_copy, returned=False).exists():
            raise serializers.ValidationError("This copy is already borrowed.")

        # Set current user as student
        serializer.save(student=self.request.user)


# -----------------------------
# Student: List their own requests
# -----------------------------
class StudentBookRequestsListView(generics.ListAPIView):
    serializer_class = BookRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BookRequest.objects.filter(student=self.request.user).order_by('-request_date')


# -----------------------------
# Admin: List all pending requests
# -----------------------------
class AdminBookRequestsListView(generics.ListAPIView):
    serializer_class = BookRequestSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return BookRequest.objects.all().order_by('-request_date')


# -----------------------------
# Admin: Approve or reject a request
# -----------------------------
class BookRequestUpdateStatusView(generics.UpdateAPIView):
    queryset = BookRequest.objects.all()
    serializer_class = BookRequestSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['patch']  # only allow PATCH

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        status_value = request.data.get('status')
        admin_comment = request.data.get('admin_comment', '')

        if status_value not in ['APPROVED', 'REJECTED']:
            return Response(
                {"error": "Status must be APPROVED or REJECTED."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Approve
        if status_value == 'APPROVED':
            # Check available copies
            book_copy = instance.book_copy
            book = book_copy.book
            if book.available_copies < 1:
                return Response(
                    {"error": "No available copies to borrow."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create BorrowRecord
            BorrowRecord.objects.create(student=instance.student, book_copy=book_copy)

            # Decrease available copies
            book.available_copies -= 1
            book.save()

        # Update request status
        instance.status = status_value
        instance.admin_comment = admin_comment
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ApproveBookRequestView(generics.UpdateAPIView):
    queryset = BookRequest.objects.all()
    serializer_class = BookRequestSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only admins should access
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        book_request = self.get_object()

        # Only admins can approve
        if request.user.role != "ADMIN":
            return Response(
                {"error": "Only admins can approve requests."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if book_request.status != "PENDING":
            return Response(
                {"error": "This request has already been processed."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the book copy is still available
        if book_request.book_copy.book.available_copies < 1:
            return Response(
                {"error": "No copies available to borrow."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create BorrowRecord
        BorrowRecord.objects.create(
            student=book_request.student,
            book_copy=book_request.book_copy
        )

        # Decrease available copies
        book = book_request.book_copy.book
        book.available_copies -= 1
        book.save()

        # Save details for response before deletion
        response_data = {
            "message": "Book request approved and moved to borrow records.",
            "student": book_request.student.username,
            "book": book_request.book_copy.book.title,
            "accession_no": book_request.book_copy.accession_no,
        }

        # ✅ Delete the BookRequest after approval
        book_request.delete()

        return Response(response_data, status=status.HTTP_200_OK)

from datetime import date

# views.py
class ReturnBookView(generics.UpdateAPIView):
    queryset = BorrowRecord.objects.all()
    serializer_class = BorrowRecordSerializer
    permission_classes = [permissions.IsAuthenticated]  # you can also use IsAdminUser for admin-only
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        borrow_record = self.get_object()

        # Ensure not already returned
        if borrow_record.returned:
            return Response({"error": "This book is already returned."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark as returned
        borrow_record.returned = True
        borrow_record.return_date = date.today()   # ✅ set return date to current date
        borrow_record.save()

        # Increase available copies
        book = borrow_record.book_copy.book
        book.available_copies += 1
        book.save()

        serializer = self.get_serializer(borrow_record)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AvailableBooksAPIView(APIView):
    def get(self, request):
        books = Book.objects.all()  # only available books
        serializer = BookSerializer(books, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    


class AdminBorrowRecordsAPIView(APIView):
    permission_classes = [IsAdminUser]  # Only admins can access

    def get(self, request):
        records = BorrowRecord.objects.select_related('student', 'book_copy', 'book_copy__book').all()
        serializer = BorrowRecordSerializer(records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


# List all users
class AdminUserListAPIView(APIView):
    permission_classes = [IsAdminUser]  # Only admins can access

    def get(self, request):
        users = CustomUser.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Update or Delete a user
class AdminUserDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, pk):
        try:
            return CustomUser.objects.get(pk=pk)
        except CustomUser.DoesNotExist:
            return None

    def put(self, request, pk):
        user = self.get_object(pk)
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSerializer(user, data=request.data, partial=True)  # partial=True allows partial updates
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = self.get_object(pk)
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    


    
class StudentBorrowRecordsAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Only logged-in users can access their records

    def get(self, request):
        student = request.user
        records = BorrowRecord.objects.filter(student=student).select_related('book_copy', 'book_copy__book')
        serializer = StudentBorrowRecordSerializer(records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class BookCopyDeleteAPIView(APIView):
    permission_classes = [IsAdminUser]  # Only admins can delete

    def delete(self, request, pk):
        try:
            book_copy = BookCopy.objects.get(pk=pk)
            book = book_copy.book  # Related book
        except BookCopy.DoesNotExist:
            return Response({"detail": "Book copy not found."}, status=status.HTTP_404_NOT_FOUND)

        # Delete the copy
        book_copy.delete()

        # Update book's total and available copies
        if book.total_copies > 0:
            book.total_copies -= 1

        if book.available_copies > 0:
            book.available_copies -= 1

        book.save()

        return Response({"detail": "Book copy deleted successfully."}, status=status.HTTP_204_NO_CONTENT)



class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token is None:
                return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()  # invalidate the token
            return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

from rest_framework.decorators import api_view

class BookSearchView(generics.ListAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        queryset = Book.objects.filter(available_copies__gt=0)  # ✅ only books with available copies

        query = self.request.query_params.get("q", None)
        if query:
            queryset = queryset.filter(
                title__icontains=query
            ) | queryset.filter(
                author__icontains=query
            ) | queryset.filter(
                category__icontains=query
            ) | queryset.filter(
                isbn__icontains=query
            ) | queryset.filter(
                publisher__icontains=query
            )

        return queryset
    

# Custom admin-only permission
class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ADMIN"


class AdminBookListView(generics.ListAPIView):
    queryset = Book.objects.all().order_by("title")
    serializer_class = BookSerializer
    permission_classes = [IsAdminUser]



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def scanner_borrow_api(request):
    """
    API for scanner workflow:
    1. Takes accession_no and student_username
    2. Creates BookRequest + BorrowRecord
    3. Decreases available copies
    """
    accession_no = request.data.get('accession_no')
    student_username = request.data.get('student_username')

    # 1️⃣ Validate student
    try:
        student = CustomUser.objects.get(username=student_username, role='MEMBER')
    except CustomUser.DoesNotExist:
        return Response({"error": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

    # 2️⃣ Validate book copy
    try:
        book_copy = BookCopy.objects.get(accession_no=accession_no)
    except BookCopy.DoesNotExist:
        return Response({"error": "Book copy not found."}, status=status.HTTP_404_NOT_FOUND)

    # 3️⃣ Check if already borrowed
    if BorrowRecord.objects.filter(book_copy=book_copy, returned=False).exists():
        return Response({"error": "This book copy is already borrowed."}, status=status.HTTP_400_BAD_REQUEST)

    # 4️⃣ Create BookRequest (directly approved)
    book_request = BookRequest.objects.create(
        student=student,
        book_copy=book_copy,
        status='APPROVED',  # Direct approval
        admin_comment="Issued via scanner."
    )

    # 5️⃣ Create BorrowRecord
    borrow_record = BorrowRecord.objects.create(
        student=student,
        book_copy=book_copy
    )

    # 6️⃣ Decrease available copies
    book = book_copy.book
    if book.available_copies > 0:
        book.available_copies -= 1
        book.save()
    else:
        return Response({"error": "No available copies left."}, status=status.HTTP_400_BAD_REQUEST)

    # 7️⃣ Return response
    return Response({
        "message": "Book issued successfully via scanner.",
        "student": student.username,
        "book_title": book.title,
        "accession_no": book_copy.accession_no,
        "borrow_id": borrow_record.id,
        "request_id": book_request.id,
        "available_copies": book.available_copies
    })



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def scanner_return_api(request):
    """
    API for marking a borrowed book as returned.
    Accepts:
    - accession_no
    - student_username
    """
    accession_no = request.data.get('accession_no')
    student_username = request.data.get('student_username')

    # 1️⃣ Validate student
    try:
        student = CustomUser.objects.get(username=student_username, role='MEMBER')
    except CustomUser.DoesNotExist:
        return Response({"error": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

    # 2️⃣ Validate book copy
    try:
        book_copy = BookCopy.objects.get(accession_no=accession_no)
    except BookCopy.DoesNotExist:
        return Response({"error": "Book copy not found."}, status=status.HTTP_404_NOT_FOUND)

    # 3️⃣ Find active borrow record
    try:
        borrow_record = BorrowRecord.objects.get(student=student, book_copy=book_copy, returned=False)
    except BorrowRecord.DoesNotExist:
        return Response({"error": "No active borrow record found for this student and book."},
                        status=status.HTTP_404_NOT_FOUND)

    # 4️⃣ Mark as returned
    borrow_record.returned = True
    borrow_record.save()

    # 5️⃣ Increase available copies
    book = book_copy.book
    book.available_copies += 1
    book.save()

    # 6️⃣ Return response
    return Response({
        "message": "Book returned successfully via scanner.",
        "student": student.username,
        "book_title": book.title,
        "accession_no": book_copy.accession_no,
        "available_copies": book.available_copies
    })



class MyNotifications(ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(student=self.request.user).order_by('-created_at')