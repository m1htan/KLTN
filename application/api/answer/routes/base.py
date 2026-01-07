import datetime
import json
import logging
from typing import Any, Dict, Generator, List, Optional
import time

from flask import jsonify, make_response, Response
from flask_restx import Namespace

from application.api.answer.services.conversation_service import ConversationService
from application.core.model_utils import (
    get_api_key_for_provider,
    get_default_model_id,
    get_provider_from_model_id,
)
from application.retriever.legal_query_analyzer import analyze_legal_query
from application.retriever.law_resolver import resolve_law_meta

from application.core.mongo_db import MongoDB
from application.core.settings import settings
from application.llm.llm_creator import LLMCreator
from application.utils import check_required_fields

logger = logging.getLogger(__name__)


answer_ns = Namespace("answer", description="Answer related operations", path="/")


class BaseAnswerResource:
    """Shared base class for answer endpoints"""

    def __init__(self):
        mongo = MongoDB.get_client()
        db = mongo[settings.MONGO_DB_NAME]
        self.db = db
        self.user_logs_collection = db["user_logs"]
        self.default_model_id = get_default_model_id()
        self.conversation_service = ConversationService()

    def validate_request(
        self, data: Dict[str, Any], require_conversation_id: bool = False
    ) -> Optional[Response]:
        """Common request validation"""
        required_fields = ["question"]
        if require_conversation_id:
            required_fields.append("conversation_id")
        if missing_fields := check_required_fields(data, required_fields):
            return missing_fields
        return None

    def check_usage(self, agent_config: Dict) -> Optional[Response]:
        """Check if there is a usage limit and if it is exceeded

        Args:
            agent_config: The config dict of agent instance

        Returns:
            None or Response if either of limits exceeded.

        """
        api_key = agent_config.get("user_api_key")
        if not api_key:
            return None
        agents_collection = self.db["agents"]
        agent = agents_collection.find_one({"key": api_key})

        if not agent:
            return make_response(
                jsonify({"success": False, "message": "Invalid API key."}), 401
            )
        limited_token_mode_raw = agent.get("limited_token_mode", False)
        limited_request_mode_raw = agent.get("limited_request_mode", False)

        limited_token_mode = (
            limited_token_mode_raw
            if isinstance(limited_token_mode_raw, bool)
            else limited_token_mode_raw == "True"
        )
        limited_request_mode = (
            limited_request_mode_raw
            if isinstance(limited_request_mode_raw, bool)
            else limited_request_mode_raw == "True"
        )

        token_limit = int(
            agent.get("token_limit", settings.DEFAULT_AGENT_LIMITS["token_limit"])
        )
        request_limit = int(
            agent.get("request_limit", settings.DEFAULT_AGENT_LIMITS["request_limit"])
        )

        token_usage_collection = self.db["token_usage"]

        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(hours=24)

        match_query = {
            "timestamp": {"$gte": start_date, "$lte": end_date},
            "api_key": api_key,
        }

        if limited_token_mode:
            token_pipeline = [
                {"$match": match_query},
                {
                    "$group": {
                        "_id": None,
                        "total_tokens": {
                            "$sum": {"$add": ["$prompt_tokens", "$generated_tokens"]}
                        },
                    }
                },
            ]
            token_result = list(token_usage_collection.aggregate(token_pipeline))
            daily_token_usage = token_result[0]["total_tokens"] if token_result else 0
        else:
            daily_token_usage = 0
        if limited_request_mode:
            daily_request_usage = token_usage_collection.count_documents(match_query)
        else:
            daily_request_usage = 0
        if not limited_token_mode and not limited_request_mode:
            return None
        token_exceeded = (
            limited_token_mode and token_limit > 0 and daily_token_usage >= token_limit
        )
        request_exceeded = (
            limited_request_mode
            and request_limit > 0
            and daily_request_usage >= request_limit
        )

        if token_exceeded or request_exceeded:
            return make_response(
                jsonify(
                    {
                        "success": False,
                        "message": "Exceeding usage limit, please try again later.",
                    }
                ),
                429,
            )
        return None

    def _sse(self, payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _early_end(self, message: str, conversation_id: Optional[str] = None) -> Generator[str, None, None]:
        # Always emit id then answer then end (to keep /api/answer stable)
        logger.info("[SSE] early_end start")
        yield self._sse({"type": "id", "id": str(conversation_id or "")})
        yield self._sse({"type": "answer", "answer": message})
        yield self._sse({"type": "end"})
        logger.info("[SSE] early_end end")

    def complete_stream(
        self,
        question: str,
        agent: Any,
        conversation_id: Optional[str],
        user_api_key: Optional[str],
        decoded_token: Dict[str, Any],
        isNoneDoc: bool = False,
        index: Optional[int] = None,
        should_save_conversation: bool = True,
        attachment_ids: Optional[List[str]] = None,
        agent_id: Optional[str] = None,
        is_shared_usage: bool = False,
        shared_token: Optional[str] = None,
        model_id: Optional[str] = None,
        override_answer=None,
    ) -> Generator[str, None, None]:
        """
        Generator function that streams the complete conversation response.

        Args:
            question: The user's question
            agent: The agent instance
            retriever: The retriever instance
            conversation_id: Existing conversation ID
            user_api_key: User's API key if any
            decoded_token: Decoded JWT token
            isNoneDoc: Flag for document-less responses
            index: Index of message to update
            should_save_conversation: Whether to persist the conversation
            attachment_ids: List of attachment IDs
            agent_id: ID of agent used
            is_shared_usage: Flag for shared agent usage
            shared_token: Token for shared agent
            model_id: Model ID used for the request
            retrieved_docs: Pre-fetched documents for sources (optional)

        Yields:
            Server-sent event strings
        """

        # OVERRIDE ANSWER (LEGAL VALIDATION BLOCK)
        if override_answer:
            yield from self._early_end(str(override_answer), conversation_id=None)
            return

        yield self._sse({"type": "start"})

        logger.info("[COMPLETE_STREAM] enter")
        yield self._sse({"type": "debug", "msg": "entered_complete_stream"})

        try:
            logger.info("[LEGAL_GUARD] start")

            # LEGAL GUARD (NO HALLUCINATION / NO CROSS-LAW MIX)
            parsed = analyze_legal_query(question)
            law_meta = resolve_law_meta(question)

            has_structured_ref = bool(parsed.get("has_structured_ref"))
            article_no = parsed.get("article_no")
            clause_no = parsed.get("clause_no")
            point_label = parsed.get("point_label")

            resolved_law_id = getattr(law_meta, "law_id", None)

            if has_structured_ref and not resolved_law_id:
                logger.warning("[LEGAL_GUARD] blocked: structured_ref but cannot resolve law_id")
                msg = (
                    "Câu hỏi của bạn có dạng Điều/Khoản/Điểm nhưng chưa xác định được văn bản luật cụ thể trong hệ thống. "
                    "Vui lòng nêu rõ tên văn bản (ví dụ: Bộ luật Hình sự 100/2015/QH13) hoặc cung cấp số/ký hiệu để tra cứu chính xác."
                )
                yield from self._early_end(msg, conversation_id=None)
                return

            if has_structured_ref and resolved_law_id:
                retrieved_docs = getattr(agent, "retrieved_docs", None) or []

                # retrieved_docs trong hệ thống bạn là list[dict] (từ StreamProcessor.create_agent)
                # Mỗi doc có dạng {"text": ..., "metadata": {...}}
                def _doc_matches(d: Dict[str, Any]) -> bool:
                    meta = (d.get("metadata") or {})
                    if meta.get("law_id") != resolved_law_id:
                        return False
                    if article_no is not None and meta.get("article_no") is not None:
                        if int(meta.get("article_no")) != int(article_no):
                            return False
                    if clause_no is not None and meta.get("clause_no") is not None:
                        if int(meta.get("clause_no")) != int(clause_no):
                            return False
                    # point có thể lưu meta["point"] hoặc meta["point_label"]
                    if point_label is not None:
                        pv = meta.get("point") or meta.get("point_label")
                        if pv is not None and str(pv).lower() != str(point_label).lower():
                            return False
                    return True

                if not retrieved_docs:
                    logger.warning("[LEGAL_GUARD] blocked: no retrieved_docs for structured query")
                    msg = (
                        "Hệ thống không truy xuất được đoạn luật phù hợp để trả lời chính xác cho Điều/Khoản/Điểm bạn hỏi. "
                        "Vui lòng kiểm tra dữ liệu đã ingest chưa hoặc thử lại sau khi build lại index/graph."
                    )
                    yield from self._early_end(msg, conversation_id=None)
                    return

                # Nếu có docs mà không doc nào match -> chặn
                if retrieved_docs and not any(_doc_matches(d) for d in retrieved_docs):

                    logger.warning(
                        "[LEGAL_GUARD] blocked: retrieved_docs mismatch (law_id/article/clause/point). "
                        f"resolved_law_id={resolved_law_id} article={article_no} clause={clause_no} point={point_label}"
                    )

                    # message rõ ràng, không cho model bịa/đưa ví dụ
                    msg = (
                        "Không tìm thấy nội dung khớp đúng Điều/Khoản/Điểm trong văn bản bạn nêu (theo dữ liệu hệ thống hiện tại). "
                        "Hệ thống sẽ không suy diễn từ luật khác. "
                        "Vui lòng kiểm tra lại số Điều/Khoản/Điểm hoặc kiểm tra dữ liệu ingest/metadata (law_id, article_no, clause_no, point)."
                    )
                    yield from self._early_end(msg, conversation_id=None)
                    return

                # Nếu không có retrieved_docs thì cũng chặn với structured query (tránh model tự bịa)
                if not retrieved_docs:
                    msg = (
                        "Hệ thống không truy xuất được đoạn luật phù hợp để trả lời chính xác cho Điều/Khoản/Điểm bạn hỏi. "
                        "Vui lòng kiểm tra dữ liệu đã ingest chưa hoặc thử lại sau khi build lại index/graph."
                    )
                    yield from self._early_end(msg, conversation_id=None)
                    return

            logger.info("[LEGAL_GUARD] pass")

            response_full, thought, source_log_docs, tool_calls = "", "", [], []
            is_structured = False
            schema_info = None
            structured_chunks = []

            logger.info("[STREAM] entering agent.gen()")

            logger.info("[STREAM] calling agent.gen() now")
            first_token_ts = None

            start = time.time()

            for line in agent.gen(query=question):
                if first_token_ts is None:
                    first_token_ts = time.time()
                    logger.info("[STREAM] first yield after %.2fs", first_token_ts - start)
                if "answer" in line:
                    response_full += str(line["answer"])
                    if line.get("structured"):
                        is_structured = True
                        schema_info = line.get("schema")
                        structured_chunks.append(line["answer"])
                        if time.time() - start > 10:
                            logger.warning("[STREAM] agent.gen() delayed >10s before first token")
                    else:
                        data = json.dumps({"type": "answer", "answer": line["answer"]})
                        yield f"data: {data}\n\n"
                elif "sources" in line:
                    truncated_sources = []
                    source_log_docs = line["sources"]
                    for source in line["sources"]:
                        truncated_source = source.copy()
                        if "text" in truncated_source:
                            truncated_source["text"] = (
                                truncated_source["text"][:100].strip() + "..."
                            )
                        truncated_sources.append(truncated_source)
                    if truncated_sources:
                        data = json.dumps(
                            {"type": "source", "source": truncated_sources}
                        )
                        yield f"data: {data}\n\n"
                elif "tool_calls" in line:
                    tool_calls = line["tool_calls"]
                    data = json.dumps({"type": "tool_calls", "tool_calls": tool_calls})
                    yield f"data: {data}\n\n"
                elif "thought" in line:
                    thought += line["thought"]
                    data = json.dumps({"type": "thought", "thought": line["thought"]})
                    yield f"data: {data}\n\n"
                elif "type" in line:
                    data = json.dumps(line)
                    yield f"data: {data}\n\n"
            if is_structured and structured_chunks:
                structured_data = {
                    "type": "structured_answer",
                    "answer": response_full,
                    "structured": True,
                    "schema": schema_info,
                }
                data = json.dumps(structured_data)
                yield f"data: {data}\n\n"
            if isNoneDoc:
                for doc in source_log_docs:
                    doc["source"] = "None"
            provider = (
                get_provider_from_model_id(model_id)
                if model_id
                else settings.LLM_PROVIDER
            )
            system_api_key = get_api_key_for_provider(provider or settings.LLM_PROVIDER)

            llm = LLMCreator.create_llm(
                provider or settings.LLM_PROVIDER,
                api_key=system_api_key,
                user_api_key=user_api_key,
                decoded_token=decoded_token,
                model_id=model_id,
            )

            if should_save_conversation:
                conversation_id = self.conversation_service.save_conversation(
                    conversation_id,
                    question,
                    response_full,
                    thought,
                    source_log_docs,
                    tool_calls,
                    llm,
                    model_id or self.default_model_id,
                    decoded_token,
                    index=index,
                    api_key=user_api_key,
                    agent_id=agent_id,
                    is_shared_usage=is_shared_usage,
                    shared_token=shared_token,
                    attachment_ids=attachment_ids,
                )
                # Persist compression metadata/summary if it exists and wasn't saved mid-execution
                compression_meta = getattr(agent, "compression_metadata", None)
                compression_saved = getattr(agent, "compression_saved", False)
                if conversation_id and compression_meta and not compression_saved:
                    try:
                        self.conversation_service.update_compression_metadata(
                            conversation_id, compression_meta
                        )
                        self.conversation_service.append_compression_message(
                            conversation_id, compression_meta
                        )
                        agent.compression_saved = True
                        logger.info(
                            f"Persisted compression metadata for conversation {conversation_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to persist compression metadata: {str(e)}",
                            exc_info=True,
                        )
            else:
                conversation_id = None
            id_data = {"type": "id", "id": str(conversation_id)}
            data = json.dumps(id_data)
            yield f"data: {data}\n\n"

            log_data = {
                "action": "stream_answer",
                "level": "info",
                "user": decoded_token.get("sub"),
                "api_key": user_api_key,
                "question": question,
                "response": response_full,
                "sources": source_log_docs,
                "attachments": attachment_ids,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
            }
            if is_structured:
                log_data["structured_output"] = True
                if schema_info:
                    log_data["schema"] = schema_info
            # Clean up text fields to be no longer than 10000 characters

            for key, value in log_data.items():
                if isinstance(value, str) and len(value) > 10000:
                    log_data[key] = value[:10000]
            self.user_logs_collection.insert_one(log_data)

            data = json.dumps({"type": "end"})
            yield f"data: {data}\n\n"
        except GeneratorExit:
            logger.info(f"Stream aborted by client for question: {question[:50]}... ")
            # Save partial response

            if should_save_conversation and response_full:
                try:
                    if isNoneDoc:
                        for doc in source_log_docs:
                            doc["source"] = "None"
                    llm = LLMCreator.create_llm(
                        settings.LLM_PROVIDER,
                        api_key=settings.API_KEY,
                        user_api_key=user_api_key,
                        decoded_token=decoded_token,
                    )
                    self.conversation_service.save_conversation(
                        conversation_id,
                        question,
                        response_full,
                        thought,
                        source_log_docs,
                        tool_calls,
                        llm,
                        model_id or self.default_model_id,
                        decoded_token,
                        index=index,
                        api_key=user_api_key,
                        agent_id=agent_id,
                        is_shared_usage=is_shared_usage,
                        shared_token=shared_token,
                        attachment_ids=attachment_ids,
                    )
                    compression_meta = getattr(agent, "compression_metadata", None)
                    compression_saved = getattr(agent, "compression_saved", False)
                    if conversation_id and compression_meta and not compression_saved:
                        try:
                            self.conversation_service.update_compression_metadata(
                                conversation_id, compression_meta
                            )
                            self.conversation_service.append_compression_message(
                                conversation_id, compression_meta
                            )
                            agent.compression_saved = True
                            logger.info(
                                f"Persisted compression metadata for conversation {conversation_id} (partial stream)"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to persist compression metadata (partial stream): {str(e)}",
                                exc_info=True,
                            )
                except Exception as e:
                    logger.error(
                        f"Error saving partial response: {str(e)}", exc_info=True
                    )
            raise
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}", exc_info=True)
            data = json.dumps(
                {
                    "type": "error",
                    "error": "Please try again later. We apologize for any inconvenience.",
                }
            )
            yield f"data: {data}\n\n"
            return

    def process_response_stream(self, stream):
        """Process the stream response for non-streaming endpoint"""
        conversation_id = ""
        response_full = ""
        source_log_docs = []
        tool_calls = []
        thought = ""
        stream_ended = False
        is_structured = False
        schema_info = None

        for line in stream:
            try:
                event_data = line.replace("data: ", "").strip()
                event = json.loads(event_data)

                if event["type"] == "id":
                    conversation_id = event["id"]
                elif event["type"] == "answer":
                    response_full += event["answer"]
                elif event["type"] == "structured_answer":
                    response_full = event["answer"]
                    is_structured = True
                    schema_info = event.get("schema")
                elif event["type"] == "source":
                    source_log_docs = event["source"]
                elif event["type"] == "tool_calls":
                    tool_calls = event["tool_calls"]
                elif event["type"] == "thought":
                    thought = event["thought"]
                elif event["type"] == "error":
                    logger.error(f"Error from stream: {event['error']}")
                    return None, None, None, None, event["error"], None
                elif event["type"] == "end":
                    stream_ended = True
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parsing stream event: {e}, line: {line}")
                continue
        if not stream_ended:
            logger.error("Stream ended unexpectedly without an 'end' event.")
            return None, None, None, None, "Stream ended unexpectedly", None
        result = (
            conversation_id,
            response_full,
            source_log_docs,
            tool_calls,
            thought,
            None,
        )

        if is_structured:
            result = result + ({"structured": True, "schema": schema_info},)
        return result

    def error_stream_generate(self, err_response):
        data = json.dumps({"type": "error", "error": err_response})
        yield f"data: {data}\n\n"
