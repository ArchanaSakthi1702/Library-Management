from django.urls import path
from .views import (RegisterUserView,UserLoginView,BookCreateView,BookUpdateView,
                    BookDeleteView,BookBulkDeleteView,ReturnBookView,
                        BookRequestCreateView,AvailableBooksAPIView,
    StudentBookRequestsListView,AdminBorrowRecordsAPIView,AdminUserListAPIView,AdminUserDetailAPIView,BookCopyDeleteAPIView,
    AdminBookRequestsListView,StudentBorrowRecordsAPIView,LogoutView,
    BookRequestUpdateStatusView,BookSearchView,AdminBookListView,scanner_borrow_api,scanner_return_api,
    RequestBookNotification,MyNotifications)
from . import views

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='user-login'),


    #only admin
    path('books/add/', BookCreateView.as_view(), name='add-book'),
    path('books/<int:id>/update/', BookUpdateView.as_view(), name='book-update'),
    path('books/<int:id>/delete/', BookDeleteView.as_view(), name='book-delete'),
    path('books/bulk-delete/', BookBulkDeleteView.as_view(), name='book-bulk-delete'),
    path("admin/books/", AdminBookListView.as_view(), name="admin-book-list"),
    
    path('book-copy/<int:pk>/delete/', BookCopyDeleteAPIView.as_view(), name='book-copy-delete'),
    path('admin/book-requests/', AdminBookRequestsListView.as_view(), name='admin-book-requests'),
    path('book-requests/<int:pk>/update-status/', BookRequestUpdateStatusView.as_view(), name='book-request-update-status'),
    path('users/', AdminUserListAPIView.as_view(), name='admin-users-list'),
    path('users/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-users-detail'),
    path('borrow-records/', AdminBorrowRecordsAPIView.as_view(), name='admin-borrow-records'),
    path("borrow-record/<int:id>/return/", ReturnBookView.as_view(), name="return-book"),
   

    #both students
    path('my-book-requests/', StudentBookRequestsListView.as_view(), name='student-book-requests'),
    path('book-requests/', BookRequestCreateView.as_view(), name='book-request-create'),
    path('books/available/', AvailableBooksAPIView.as_view(), name='available-books'),
    path('my-borrows/', StudentBorrowRecordsAPIView.as_view(), name='student-borrow-records'),
    path("books/search/", BookSearchView.as_view(), name="book-search"),
    path('notify-book/<int:book_id>/', RequestBookNotification.as_view(), name='request-book-notify'),
    path('my-notifications/', MyNotifications.as_view(), name='my-notifications'),


    path('scanner-borrow/', scanner_borrow_api, name='scanner-borrow'),
    path('scanner-return/', scanner_return_api, name='scanner-return'),



     path("logout/", LogoutView.as_view(), name="logout"),
]