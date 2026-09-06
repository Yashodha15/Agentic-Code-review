def serialize_user(user):
    return {
        'id': user.id,
        'display_name': user.full_name,
        'email': user.email,
    }
