from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, current_app)
from flask_login import login_required, current_user
from extensions import db
from models import Animal, ChatMessage
from wildsight_ai import get_chat_reply, is_configured
from media import save_photo
import os

wildsight = Blueprint('wildsight', __name__)


def _get_owned_animal_or_none(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    # owner or original creator may use the assistant
    if current_user.id not in (animal.owner_id, animal.created_by_id):
        return None
    return animal


@wildsight.route('/<int:animal_id>/chat')
@login_required
def chat(animal_id):
    animal = _get_owned_animal_or_none(animal_id)
    if not animal:
        flash('You do not have access to this animal.', 'danger')
        return redirect(url_for('main.dashboard'))

    messages = ChatMessage.query.filter_by(
        animal_id=animal.id, user_id=current_user.id
    ).order_by(ChatMessage.created_at).all()

    return render_template('wildsight/chat.html',
                           animal=animal,
                           messages=messages,
                           ai_ready=is_configured())


@wildsight.route('/<int:animal_id>/message', methods=['POST'])
@login_required
def message(animal_id):
    animal = _get_owned_animal_or_none(animal_id)
    if not animal:
        return jsonify({'error': 'no access'}), 403

    # supports both plain JSON (text-only) and multipart form (text + photo)
    if request.content_type and 'multipart/form-data' in request.content_type:
        user_text = request.form.get('message', '').strip()
        photo_file = request.files.get('photo')
    else:
        user_text = (request.json or {}).get('message', '').strip()
        photo_file = None

    media_filename = save_photo(photo_file) if photo_file else None

    if not user_text and not media_filename:
        return jsonify({'error': 'empty'}), 400
    if not user_text:
        user_text = "Please look at this photo and check for any signs of injury or illness."

    # load history BEFORE saving the new user message
    history = [
        {'role': m.role, 'content': m.content}
        for m in ChatMessage.query.filter_by(
            animal_id=animal.id, user_id=current_user.id
        ).order_by(ChatMessage.created_at).all()
    ]

    # save the user's message (with attached photo, if any)
    db.session.add(ChatMessage(animal_id=animal.id, user_id=current_user.id,
                               role='user', content=user_text, media_path=media_filename))
    db.session.commit()

    # get AI reply (personalised with this animal's data; vision-aware if a photo was sent)
    image_path = None
    if media_filename:
        image_path = os.path.join(current_app.root_path, 'static', 'uploads', media_filename)

    reply = get_chat_reply(animal, history, user_text, image_path=image_path)

    # save the assistant reply
    db.session.add(ChatMessage(animal_id=animal.id, user_id=current_user.id,
                               role='assistant', content=reply))
    db.session.commit()

    media_url = url_for('static', filename='uploads/' + media_filename) if media_filename else None
    return jsonify({'reply': reply, 'media_url': media_url})


@wildsight.route('/<int:animal_id>/clear', methods=['POST'])
@login_required
def clear(animal_id):
    animal = _get_owned_animal_or_none(animal_id)
    if not animal:
        return jsonify({'error': 'no access'}), 403
    ChatMessage.query.filter_by(
        animal_id=animal.id, user_id=current_user.id
    ).delete()
    db.session.commit()
    return jsonify({'ok': True})
