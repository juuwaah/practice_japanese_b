from flask import Blueprint, render_template, session
from flask_login import login_required

drive_quiz_bp = Blueprint('drive_quiz', __name__, url_prefix='/drive_quiz')

@drive_quiz_bp.route('/', methods=['GET', 'POST'])
@login_required
def drive_quiz_index():
    return 'Drive quiz: Hello World!' 