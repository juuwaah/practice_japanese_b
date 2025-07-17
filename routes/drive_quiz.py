from flask import Blueprint, render_template
from flask_login import login_required

listening_quiz_bp = Blueprint('listening_quiz', __name__, url_prefix='/listening_quiz')

@listening_quiz_bp.route('/', methods=['GET', 'POST'])
@login_required
def listening_quiz_index():
    return 'Listening quiz: Hello World!' 