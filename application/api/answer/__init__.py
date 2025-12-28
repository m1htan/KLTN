from flask import Blueprint

from application.api import api
from application.api.answer.routes.answer import AnswerResource
from application.api.answer.routes.base import answer_ns
from application.api.answer.routes.stream import StreamResource


answer = Blueprint("answer", __name__)

api.add_namespace(answer_ns)

