import logging
import traceback

from flask import request, Response
from flask_restx import fields, Resource

from application.api import api
from application.api.answer.routes.base import answer_ns, BaseAnswerResource
from application.retriever.legal_structure_validator import validate_legal_structure
from application.knowledge_graph.neo4j_client import load_neo4j_config_from_env, Neo4jClient
from application.api.answer.services.stream_processor import StreamProcessor

logger = logging.getLogger(__name__)


@answer_ns.route("/stream")
class StreamResource(Resource, BaseAnswerResource):
    def __init__(self, *args, **kwargs):
        Resource.__init__(self, *args, **kwargs)
        BaseAnswerResource.__init__(self)

    stream_model = answer_ns.model(
        "StreamModel",
        {
            "question": fields.String(
                required=True, description="Question to be asked"
            ),
            "history": fields.List(
                fields.String,
                required=False,
                description="Conversation history (only for new conversations)",
            ),
            "conversation_id": fields.String(
                required=False,
                description="Existing conversation ID (loads history)",
            ),
            "prompt_id": fields.String(
                required=False, default="default", description="Prompt ID"
            ),
            "chunks": fields.Integer(
                required=False, default=2, description="Number of chunks"
            ),
            "token_limit": fields.Integer(required=False, description="Token limit"),
            "retriever": fields.String(required=False, description="Retriever type"),
            "api_key": fields.String(required=False, description="API key"),
            "active_docs": fields.String(
                required=False, description="Active documents"
            ),
            "isNoneDoc": fields.Boolean(
                required=False, description="Flag indicating if no document is used"
            ),
            "index": fields.Integer(
                required=False, description="Index of the query to update"
            ),
            "save_conversation": fields.Boolean(
                required=False,
                default=True,
                description="Whether to save the conversation",
            ),
            "model_id": fields.String(
                required=False,
                description="Model ID to use for this request",
            ),
            "attachments": fields.List(
                fields.String, required=False, description="List of attachment IDs"
            ),
            "passthrough": fields.Raw(
                required=False,
                description="Dynamic parameters to inject into prompt template",
            ),
        },
    )

    @api.expect(stream_model)
    @api.doc(description="Stream a response based on the question and retriever")
    def post(self):
        data = request.get_json()
        if error := self.validate_request(data, "index" in data):
            return error
        decoded_token = getattr(request, "decoded_token", None)
        processor = StreamProcessor(data, decoded_token)
        try:
            logger.info("[STREAM] initialize processor")
            processor.initialize()

            logger.info("[STREAM] pre_fetch_docs start")
            docs_together, docs_list = processor.pre_fetch_docs(data["question"])
            logger.info("[STREAM] pre_fetch_docs done")

            # Nếu validator trả message lỗi → trả thẳng cho user
            if docs_list is None and isinstance(docs_together, str):

                logger.info("[STREAM] returning override_answer SSE")

                return Response(
                    self.complete_stream(
                        question=data["question"],
                        agent=None,
                        conversation_id=processor.conversation_id,
                        user_api_key=processor.agent_config.get("user_api_key"),
                        decoded_token=processor.decoded_token,
                        isNoneDoc=True,
                        index=data.get("index"),
                        should_save_conversation=False,
                        model_id=processor.model_id,
                        override_answer=docs_together,
                    ),
                    mimetype="text/event-stream",
                )

            logger.info("[STREAM] pre_fetch_tools start")
            tools_data = processor.pre_fetch_tools()
            logger.info("[STREAM] pre_fetch_tools done")

            logger.info("[STREAM] create_agent start")
            agent = processor.create_agent(
                docs_together=docs_together, docs=docs_list, tools_data=tools_data
            )
            logger.info("[STREAM] create_agent done")

            logger.info("[STREAM] start complete_stream")

            if error := self.check_usage(processor.agent_config):
                return error
            return Response(
                self.complete_stream(
                    question=data["question"],
                    agent=agent,
                    conversation_id=processor.conversation_id,
                    user_api_key=processor.agent_config.get("user_api_key"),
                    decoded_token=processor.decoded_token,
                    isNoneDoc=data.get("isNoneDoc"),
                    index=data.get("index"),
                    should_save_conversation=data.get("save_conversation", True),
                    attachment_ids=data.get("attachments", []),
                    agent_id=data.get("agent_id"),
                    is_shared_usage=processor.is_shared_usage,
                    shared_token=processor.shared_token,
                    model_id=processor.model_id,
                ),
                mimetype="text/event-stream",
            )
        except ValueError as e:
            message = "Malformed request body"
            logger.error(
                f"/stream - error: {message} - specific error: {str(e)} - traceback: {traceback.format_exc()}",
                extra={"error": str(e), "traceback": traceback.format_exc()},
            )
            return Response(
                self.error_stream_generate(message),
                status=400,
                mimetype="text/event-stream",
            )
        except Exception as e:
            logger.error(
                f"/stream - error: {str(e)} - traceback: {traceback.format_exc()}",
                extra={"error": str(e), "traceback": traceback.format_exc()},
            )
            return Response(
                self.error_stream_generate("Unknown error occurred"),
                status=400,
                mimetype="text/event-stream",
            )
