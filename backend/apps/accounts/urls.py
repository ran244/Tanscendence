from django.urls import path

from apps.accounts import views

urlpatterns = [
    # Authentication
    path("auth/register/", views.register, name="register"),
    path("auth/email/verify/", views.verify_email, name="verify_email"),
    path("auth/email/resend/", views.resend_email_verification, name="resend_email_verification"),
    path("auth/login/", views.login, name="login"),
    path("auth/2fa/verify/", views.verify_two_fa, name="two_fa_verify"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/logout/", views.logout, name="logout"),
    path("auth/password/change/", views.password_change, name="password_change"),
    path("auth/password/reset/request/", views.password_reset_request, name="password_reset_request"),
    path("auth/password/reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    # Own profile
    path("me/", views.me, name="me"),
    path("me/avatar/", views.avatar, name="avatar"),
    path("me/2fa/setup/", views.two_fa_setup, name="two_fa_setup"),
    path("me/2fa/enable/", views.two_fa_enable, name="two_fa_enable"),
    path("me/2fa/disable/", views.two_fa_disable, name="two_fa_disable"),
    path("me/delete/", views.delete_account, name="delete_account"),
    # Public profiles
    path("users/", views.user_search, name="user_search"),
    path("users/<int:user_id>/", views.public_profile, name="public_profile"),
    # Friends
    path("friends/", views.friends_list, name="friends_list"),
    path("friends/requests/", views.friend_requests, name="friend_requests"),
    path("friends/request/", views.friend_request_send, name="friend_request_send"),
    path("friends/requests/<int:friendship_id>/accept/", views.friend_request_accept, name="friend_request_accept"),
    path("friends/requests/<int:friendship_id>/decline/", views.friend_request_decline, name="friend_request_decline"),
    path("friends/<int:user_id>/", views.friend_remove, name="friend_remove"),
    path("presence/", views.presence_status, name="presence_status"),
    # Admin
    path("admin/users/", views.admin_users, name="admin_users"),
    path("admin/users/<int:user_id>/", views.admin_user_update, name="admin_user_update"),
    path("admin/users/<int:user_id>/block/", views.admin_user_block, name="admin_user_block"),
    path("admin/users/<int:user_id>/unblock/", views.admin_user_unblock, name="admin_user_unblock"),
]
