from datetime import datetime
import uuid


# Note class
class Note():

    def __init__(self, title, body, user_id, user_name, id="", deleted=False, tags=None):
        self.title = title
        self.body = body
        self.user_id = user_id
        self.user_name = user_name
        self.tags = list(tags) if tags else []
        self.timestamp = datetime.utcnow()
        self.date_string = self.timestamp.strftime("%-d %b %Y")
        self.id = uuid.uuid4().hex if not id else id
        self.deleted = deleted

    # Return dictionary representation of object
    def dict(self):
        return {
            "title": self.title,
            "body": self.body,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "date_string": self.date_string,
            "id": self.id,
            "deleted": self.deleted
        }
