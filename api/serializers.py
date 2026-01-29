from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import CustomUser,Book,BookCopy,BookRequest,BorrowRecord,BookNotificationRequest,Notification,EBook,EBookBookmark
from cloudinary.utils import cloudinary_url

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'password', 'role']

    def validate(self, attrs):
        role = attrs.get("role")
        username = attrs.get("username")

        if role == "MEMBER":
            # Username must follow roll number format, e.g., "CS2025001"
            if not username:
                raise serializers.ValidationError({"username": "Roll number is required for students."})
        elif role == "ADMIN":
            if not username:
                raise serializers.ValidationError({"username": "Username is required for admin."})
        return attrs

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return CustomUser.objects.create(**validated_data)
    

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = ["id"]


class BookCopySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCopy
        fields = ["id", "accession_no"]

class BookSerializer(serializers.ModelSerializer):
    available_copy_ids = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True) 
    copies = BookCopySerializer(many=True, read_only=True)  # ✅ full copies

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "isbn",
            "category",
            "publisher",
            "description",
            "image",
            "total_copies",
            "available_copies",
            "available_copy_ids",
            "copies",   # ✅ include all copies
        ]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def get_available_copy_ids(self, obj):
        all_copies = obj.copies.all().order_by("id")
        available_copies = all_copies[:obj.available_copies]
        return [copy.id for copy in available_copies]
    
    def to_representation(self, obj):
        """Override to return absolute image URL in response"""
        rep = super().to_representation(obj)
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            rep["image"] = request.build_absolute_uri(obj.image.url) if request else obj.image.url
        else:
            rep["image"] = None
        return rep


from rest_framework import serializers
from .models import BookRequest, BorrowRecord

class BookRequestSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book_copy.book.title", read_only=True)
    book_author = serializers.CharField(source="book_copy.book.author", read_only=True)
    book_description = serializers.CharField(source="book_copy.book.description", read_only=True)

    class Meta:
        model = BookRequest
        fields = [
            'id',
            'student',
            'book_copy',
            'book_title',
            'book_author',
            'book_description',
            'request_date',
            'status',
            'admin_comment',
        ]
        read_only_fields = ['student', 'status', 'request_date', 'admin_comment']

    def validate_book_copy(self, value):
        # Check if the book copy is already borrowed
        borrowed = BorrowRecord.objects.filter(book_copy=value, returned=False).exists()
        if borrowed:
            raise serializers.ValidationError("This copy is already borrowed.")
        return value
        

# serializers.py
class BorrowRecordSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)
    book_title = serializers.CharField(source='book_copy.book.title', read_only=True)
    accession_no = serializers.CharField(source='book_copy.accession_no', read_only=True)
    fine = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)  # ✅ NEW

    class Meta:
        model = BorrowRecord
        fields = [
            "id",
            "student_username",
            "book_title",
            "accession_no",
            "borrow_date",
            "return_date",
            "returned",
            "fine",    # ✅ Include fine here
        ]



class StudentBorrowRecordSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book_copy.book.title', read_only=True)
    accession_no = serializers.CharField(source='book_copy.accession_no', read_only=True)
    fine = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)  # ✅ NEW

    class Meta:
        model = BorrowRecord
        fields = [
            "id",
            "book_title",
            "accession_no",
            "borrow_date",
            "return_date",
            "returned",
            "fine",   # ✅ Include fine here
        ]



class BookNotificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookNotificationRequest
        fields = ['id', 'student', 'book', 'notified']
        read_only_fields = ['student', 'notified']




class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'read', 'created_at']



class EBookSerializer(serializers.ModelSerializer):
    ebook_file = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = EBook
        fields = "__all__"

    def get_ebook_file(self, obj):
        if not obj.ebook_file:
            return None
        # Add the proper file extension
        file_format = obj.format.lower()  # 'pdf' or 'epub'
        url, _ = cloudinary_url(
            obj.ebook_file.public_id,
            resource_type='raw',
            format=file_format  # ensures .pdf or .epub is in the URL
        )
        return url

    def get_cover_image(self, obj):
        if not obj.cover_image:
            return None
        # Ensure the image has proper extension (jpg/png)
        # Use the original format if stored, or force jpg
        url, _ = cloudinary_url(
            obj.cover_image.public_id,
            format='jpg'  # you can also use 'png' if your images are PNG
        )
        return url
    
class EBookBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = EBookBookmark
        fields = "__all__"
        read_only_fields = ["student"]