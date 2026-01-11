"""Form for blog post comments."""

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea


class CommentForm(FlaskForm):
    """Form for submitting comments on blog posts.

    Attributes:
        author_name: Required text field for the commenter's name.
        comment: Required text area for the comment content.
        submit: Submit button to post the comment.
    """

    author_name = StringField(str(lazy_gettext("Name")), validators=[DataRequired()])
    comment = StringField(
        str(lazy_gettext("Type comment here")),
        validators=[DataRequired()],
        widget=TextArea(),
    )
    submit = SubmitField(str(lazy_gettext("Comment")))
