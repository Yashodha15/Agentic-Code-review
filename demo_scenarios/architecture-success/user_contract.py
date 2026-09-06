def serialize_user(user):
    display_name = user.display_name or user.full_name
    return {
        'id': user.id,
        'name': display_name,
        'display_name': display_name,
        'email': user.email,
    }
